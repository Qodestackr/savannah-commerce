from django.db import models
from django.contrib.auth import get_user_model
from apps.core.models import TimeStampedModel
from apps.core.audit_middleware import AuditableMixin
from apps.products.models import Product

User = get_user_model()


class Order(AuditableMixin, TimeStampedModel):
    """Order model with advanced inventory integration."""
    
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('reserved', 'Stock Reserved'),
        ('pending', 'Pending Payment'),
        ('confirmed', 'Confirmed'),
        ('processing', 'Processing'),
        ('shipped', 'Shipped'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
        ('failed', 'Failed'),
    ]
    
    customer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders')
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    shipping_address = models.TextField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    
    # Inventory management fields
    reservation_expires_at = models.DateTimeField(null=True, blank=True)
    is_reservation_active = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['customer', 'status']),
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['reservation_expires_at']),
        ]
    
    def __str__(self):
        return f"Order #{self.id} - {self.customer.email}"
    
    @property
    def item_count(self):
        """Total number of items in the order."""
        return sum(item.quantity for item in self.items.all())
    
    @property
    def is_reservation_expired(self):
        """Check if reservation has expired."""
        if not self.reservation_expires_at:
            return False
        from django.utils import timezone
        return timezone.now() > self.reservation_expires_at
    
    def can_be_cancelled(self):
        """Check if order can be cancelled."""
        return self.status in ['draft', 'reserved', 'pending', 'confirmed']
    
    def can_be_confirmed(self):
        """Check if order can be confirmed."""
        return self.status in ['reserved', 'pending']
    
    def reserve_stock(self, expiration_minutes=30):
        """Reserve stock for this order."""
        from .services import InventoryService
        from django.utils import timezone
        from datetime import timedelta
        
        if self.status != 'draft':
            return False
        
        inventory_service = InventoryService()
        order_items = [
            {'product_id': item.product.id, 'quantity': item.quantity}
            for item in self.items.all()
        ]
        
        try:
            reservations = inventory_service.reserve_stock_for_order(
                order_items=order_items,
                order_id=str(self.id),
                expiration_minutes=expiration_minutes
            )
            
            if reservations:
                self.status = 'reserved'
                self.is_reservation_active = True
                self.reservation_expires_at = timezone.now() + timedelta(minutes=expiration_minutes)
                self.save(update_fields=['status', 'is_reservation_active', 'reservation_expires_at'])
                return True
            
        except Exception as e:
            # Log error and update status
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to reserve stock for order {self.id}: {e}")
            self.status = 'failed'
            self.save(update_fields=['status'])
        
        return False
    
    def confirm_order(self):
        """Confirm the order and convert reservations to allocations."""
        from .services import InventoryService
        
        if not self.can_be_confirmed():
            return False
        
        inventory_service = InventoryService()
        
        try:
            success = inventory_service.confirm_order_reservations(str(self.id))
            
            if success:
                self.status = 'confirmed'
                self.is_reservation_active = False
                self.save(update_fields=['status', 'is_reservation_active'])
                
                # Trigger notification tasks
                from apps.notifications.tasks import send_order_notification
                send_order_notification.delay(str(self.id))
                
                return True
                
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to confirm order {self.id}: {e}")
        
        return False
    
    def cancel_order(self, reason="Customer cancellation"):
        """Cancel the order and release any reservations."""
        from .services import InventoryService
        
        if not self.can_be_cancelled():
            return False
        
        inventory_service = InventoryService()
        
        try:
            if self.is_reservation_active:
                inventory_service.cancel_order_reservations(str(self.id))
            
            self.status = 'cancelled'
            self.is_reservation_active = False
            self.notes = f"{self.notes}\n\nCancelled: {reason}".strip()
            self.save(update_fields=['status', 'is_reservation_active', 'notes'])
            
            return True
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to cancel order {self.id}: {e}")
        
        return False
    
    def extend_reservation(self, additional_minutes=30):
        """Extend the reservation expiration time."""
        from .services import InventoryService
        from django.utils import timezone
        from datetime import timedelta
        
        if not self.is_reservation_active:
            return False
        
        inventory_service = InventoryService()
        success = inventory_service.extend_reservation(str(self.id), additional_minutes)
        
        if success:
            self.reservation_expires_at = timezone.now() + timedelta(minutes=additional_minutes)
            self.save(update_fields=['reservation_expires_at'])
            return True
        
        return False


class OrderItem(AuditableMixin, TimeStampedModel):
    """Order item model."""
    
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    
    class Meta:
        unique_together = ['order', 'product']
    
    def save(self, *args, **kwargs):
        self.total_price = self.quantity * self.unit_price
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.quantity}x {self.product.name} for Order #{self.order.id}"