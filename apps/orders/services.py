import logging
from datetime import timedelta
from typing import Dict, List, Optional, Tuple

from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone

import redis
import redis_lock

from apps.orders.models import Order, OrderItem
from apps.products.models import Product, StockMovement, StockReservation

logger = logging.getLogger(__name__)

# Redis connection for distributed locking
redis_client = redis.Redis.from_url("redis://localhost:6379/0")


class InsufficientStockError(Exception):
    """Raised when there's insufficient stock for an operation."""

    pass


class ReservationExpiredError(Exception):
    """Raised when trying to use an expired reservation."""

    pass


class InventoryService:
    """
    Advanced inventory management service inspired by Saleor.
    Handles stock reservations, allocations, and ensures data consistency.
    """

    def __init__(self):
        self.redis_client = redis_client

    def reserve_stock_for_order(
        self, order_items: List[Dict], order_id: str, expiration_minutes: int = 30
    ) -> List[StockReservation]:
        """
        Reserve stock for an order with distributed locking.

        Args:
            order_items: List of {'product_id': int, 'quantity': int}
            order_id: Unique order identifier
            expiration_minutes: How long to hold the reservation

        Returns:
            List of StockReservation objects created

        Raises:
            InsufficientStockError: If any product doesn't have enough stock
        """
        reservations = []
        product_locks = {}

        try:
            # Sort products by ID to prevent deadlocks
            sorted_items = sorted(order_items, key=lambda x: x["product_id"])

            # Acquire locks for all products first
            for item in sorted_items:
                product_id = item["product_id"]
                lock_key = f"product_lock:{product_id}"
                lock = redis_lock.Lock(self.redis_client, lock_key, timeout=60)

                if lock.acquire(blocking=True, timeout=30):
                    product_locks[product_id] = lock
                else:
                    raise ValidationError(
                        f"Could not acquire lock for product {product_id}"
                    )

            # Check stock availability for all products first
            with transaction.atomic():
                for item in sorted_items:
                    product = Product.objects.select_for_update().get(
                        id=item["product_id"]
                    )

                    if not product.can_reserve(item["quantity"]):
                        raise InsufficientStockError(
                            f"Insufficient stock for {product.name}. "
                            f"Available: {product.available_quantity}, "
                            f"Requested: {item['quantity']}"
                        )

                # If all checks pass, create reservations
                expiration_time = timezone.now() + timedelta(minutes=expiration_minutes)

                for item in sorted_items:
                    product = Product.objects.get(id=item["product_id"])

                    # Reserve the stock
                    success = product.reserve_stock(
                        item["quantity"], f"Order {order_id} reservation"
                    )

                    if success:
                        reservation = StockReservation.objects.create(
                            product=product,
                            quantity=item["quantity"],
                            order_id=order_id,
                            expires_at=expiration_time,
                            reason=f"Order {order_id}",
                        )
                        reservations.append(reservation)

                        # Log the movement
                        self._log_stock_movement(
                            product=product,
                            movement_type="RESERVE",
                            quantity=item["quantity"],
                            reason=f"Reserved for order {order_id}",
                            reference_id=order_id,
                        )
                    else:
                        # This shouldn't happen if our checks above passed
                        raise InsufficientStockError(
                            f"Failed to reserve stock for {product.name}"
                        )

        except Exception as e:
            # Release any reservations created before the error
            for reservation in reservations:
                try:
                    reservation.release()
                except Exception as cleanup_error:
                    logger.error(
                        f"Error releasing reservation during cleanup: {cleanup_error}"
                    )

            raise e

        finally:
            # Release all locks
            for lock in product_locks.values():
                try:
                    lock.release()
                except Exception as lock_error:
                    logger.error(f"Error releasing lock: {lock_error}")

        return reservations

    def confirm_order_reservations(self, order_id: str) -> bool:
        """
        Convert reservations to allocations when order is confirmed.
        """
        try:
            with transaction.atomic():
                reservations = StockReservation.objects.filter(
                    order_id=order_id, is_active=True
                ).select_related("product")

                for reservation in reservations:
                    # Move from reserved to allocated
                    success = reservation.product.allocate_stock(reservation.quantity)

                    if success:
                        # Mark reservation as used
                        reservation.is_active = False
                        reservation.save()

                        # Log the movement
                        self._log_stock_movement(
                            product=reservation.product,
                            movement_type="ALLOCATE",
                            quantity=reservation.quantity,
                            reason=f"Order {order_id} confirmed",
                            reference_id=order_id,
                        )
                    else:
                        raise ValidationError(
                            f"Failed to allocate stock for {reservation.product.name}"
                        )

                return True

        except Exception as e:
            logger.error(f"Error confirming reservations for order {order_id}: {e}")
            return False

    def cancel_order_reservations(self, order_id: str) -> bool:
        """
        Release all reservations for a cancelled order.
        """
        try:
            with transaction.atomic():
                reservations = StockReservation.objects.filter(
                    order_id=order_id, is_active=True
                ).select_related("product")

                for reservation in reservations:
                    reservation.release()

                    # Log the movement
                    self._log_stock_movement(
                        product=reservation.product,
                        movement_type="RELEASE",
                        quantity=reservation.quantity,
                        reason=f"Order {order_id} cancelled",
                        reference_id=order_id,
                    )

                return True

        except Exception as e:
            logger.error(f"Error cancelling reservations for order {order_id}: {e}")
            return False

    def fulfill_order(self, order_id: str) -> bool:
        """
        Fulfill order by reducing allocated stock and updating movement logs.
        """
        try:
            with transaction.atomic():
                order = Order.objects.get(id=order_id)

                for item in order.items.all():
                    product = item.product

                    # Reduce allocated stock
                    success = product.deallocate_stock(item.quantity)

                    if success:
                        # Also reduce total stock as it's now shipped
                        product.stock_quantity = (
                            models.F("stock_quantity") - item.quantity
                        )
                        product.save(update_fields=["stock_quantity"])

                        # Log the movement
                        self._log_stock_movement(
                            product=product,
                            movement_type="OUT",
                            quantity=-item.quantity,
                            reason=f"Order {order_id} fulfilled",
                            reference_id=order_id,
                        )
                    else:
                        raise ValidationError(
                            f"Failed to deallocate stock for {product.name}"
                        )

                return True

        except Exception as e:
            logger.error(f"Error fulfilling order {order_id}: {e}")
            return False

    def cleanup_expired_reservations(self) -> int:
        """
        Clean up expired reservations (usually run as a background task).

        Returns:
            Number of reservations cleaned up
        """
        expired_count = 0

        try:
            expired_reservations = StockReservation.objects.filter(
                expires_at__lt=timezone.now(), is_active=True
            ).select_related("product")

            for reservation in expired_reservations:
                try:
                    with transaction.atomic():
                        reservation.release()
                        expired_count += 1

                        # Log cleanups
                        self._log_stock_movement(
                            product=reservation.product,
                            movement_type="RELEASE",
                            quantity=reservation.quantity,
                            reason="Reservation expired - auto cleanup",
                            reference_id=str(reservation.order_id)
                            if reservation.order_id
                            else None,
                        )

                        logger.info(f"Released expired reservation: {reservation}")

                except Exception as e:
                    logger.error(
                        f"Error releasing expired reservation {reservation.id}: {e}"
                    )

        except Exception as e:
            logger.error(f"Error during reservation cleanup: {e}")

        return expired_count

    def get_inventory_summary(self, product_id: int) -> Dict:
        """
        Get comprehensive inventory summary for a product.
        """
        try:
            product = Product.objects.get(id=product_id)

            active_reservations = (
                StockReservation.objects.filter(
                    product=product, is_active=True
                ).aggregate(total=models.Sum("quantity"))["total"]
                or 0
            )

            recent_movements = StockMovement.objects.filter(product=product).order_by(
                "-created_at"
            )[:10]

            return {
                "product_id": product.id,
                "product_name": product.name,
                "sku": product.sku,
                "total_stock": product.stock_quantity,
                "reserved_quantity": product.reserved_quantity,
                "allocated_quantity": product.allocated_quantity,
                "available_quantity": product.available_quantity,
                "active_reservations": active_reservations,
                "is_low_stock": product.is_low_stock,
                "low_stock_threshold": product.low_stock_threshold,
                "track_inventory": product.track_inventory,
                "recent_movements": [
                    {
                        "type": mv.movement_type,
                        "quantity": mv.quantity,
                        "reason": mv.reason,
                        "created_at": mv.created_at,
                    }
                    for mv in recent_movements
                ],
            }

        except Product.DoesNotExist:
            raise ValidationError(f"Product with ID {product_id} not found")

    def adjust_stock(
        self, product_id: int, new_quantity: int, reason: str = "Manual adjustment"
    ) -> bool:
        """
        Manually adjust stock levels (admin function).
        """
        try:
            with transaction.atomic():
                product = Product.objects.select_for_update().get(id=product_id)
                old_quantity = product.stock_quantity
                difference = new_quantity - old_quantity

                product.stock_quantity = new_quantity
                product.save(update_fields=["stock_quantity"])

                # Log the adjustment
                self._log_stock_movement(
                    product=product,
                    movement_type="ADJUSTMENT",
                    quantity=difference,
                    reason=reason,
                )

                logger.info(
                    f"Stock adjusted for {product.name}: {old_quantity} -> {new_quantity} "
                    f"(difference: {difference})"
                )

                return True

        except Exception as e:
            logger.error(f"Error adjusting stock for product {product_id}: {e}")
            return False

    def _log_stock_movement(
        self,
        product: Product,
        movement_type: str,
        quantity: int,
        reason: str,
        reference_id: str = None,
    ) -> StockMovement:
        """
        Log a stock movement for audit purposes.
        """
        # Refresh product to get current stock levels
        product.refresh_from_db()

        movement = StockMovement.objects.create(
            product=product,
            movement_type=movement_type,
            quantity=quantity,
            reason=reason,
            reference_id=reference_id,
            stock_after=product.stock_quantity,
            reserved_after=product.reserved_quantity,
            allocated_after=product.allocated_quantity,
        )

        return movement

    def extend_reservation(self, order_id: str, additional_minutes: int = 30) -> bool:
        """
        Extend the expiration time for order reservations.
        """
        try:
            reservations = StockReservation.objects.filter(
                order_id=order_id, is_active=True
            )

            for reservation in reservations:
                reservation.extend_expiration(additional_minutes)

            return True

        except Exception as e:
            logger.error(f"Error extending reservations for order {order_id}: {e}")
            return False
