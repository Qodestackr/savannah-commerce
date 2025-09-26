from django.db import models
from django.utils.text import slugify
from mptt.models import MPTTModel, TreeForeignKey
from apps.core.models import TimeStampedModel
from apps.core.audit_middleware import AuditableMixin


class Category(MPTTModel, TimeStampedModel):
    """Hierarchical product categories using MPTT."""

    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    description = models.TextField(blank=True, null=True)
    parent = TreeForeignKey(
        "self", on_delete=models.CASCADE, null=True, blank=True, related_name="children"
    )
    is_active = models.BooleanField(default=True)

    class MPTTMeta:
        order_insertion_by = ["name"]

    class Meta:
        verbose_name_plural = "Categories"
        ordering = ["name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    @property
    def full_path(self):
        """Returns the full category path from root to current."""
        ancestors = self.get_ancestors(include_self=True)
        return " > ".join([ancestor.name for ancestor in ancestors])


class Product(AuditableMixin, TimeStampedModel):
    """Product model with advanced inventory management."""

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    sku = models.CharField(max_length=100, unique=True)
    category = models.ForeignKey(
        Category, on_delete=models.CASCADE, related_name="products"
    )

    # Advanced inventory fields
    stock_quantity = models.PositiveIntegerField(
        default=0, help_text="Total physical stock"
    )
    reserved_quantity = models.PositiveIntegerField(
        default=0, help_text="Stock reserved for pending orders"
    )
    allocated_quantity = models.PositiveIntegerField(
        default=0, help_text="Stock allocated for confirmed orders"
    )

    # Configuration
    is_active = models.BooleanField(default=True)
    track_inventory = models.BooleanField(
        default=True, help_text="Whether to track inventory for this product"
    )
    low_stock_threshold = models.PositiveIntegerField(
        default=10, help_text="Alert when stock falls below this level"
    )

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["sku"]),
            models.Index(fields=["category", "is_active"]),
            models.Index(fields=["stock_quantity"]),
        ]

    def __str__(self):
        return self.name

    @property
    def available_quantity(self):
        """Calculate available quantity (stock - reserved - allocated)."""
        return max(
            0, self.stock_quantity - self.reserved_quantity - self.allocated_quantity
        )

    @property
    def is_in_stock(self):
        """Check if product has available stock."""
        return self.available_quantity > 0

    @property
    def is_low_stock(self):
        """Check if product is running low on stock."""
        return self.available_quantity <= self.low_stock_threshold

    def can_reserve(self, quantity):
        """Check if we can reserve the specified quantity."""
        if not self.track_inventory:
            return True
        return self.available_quantity >= quantity

    def reserve_stock(self, quantity, reason="Order reservation"):
        """Reserve stock for an order."""
        from django.db import transaction

        if not self.track_inventory:
            return True

        with transaction.atomic():
            # Refresh from database to get latest values
            product = Product.objects.select_for_update().get(id=self.id)

            if product.available_quantity >= quantity:
                product.reserved_quantity = models.F("reserved_quantity") + quantity
                product.save(update_fields=["reserved_quantity"])

                # Log the reservation
                StockReservation.objects.create(
                    product=product, quantity=quantity, reason=reason
                )
                return True
            return False

    def release_reservation(self, quantity):
        """Release reserved stock."""
        from django.db import transaction

        if not self.track_inventory:
            return True

        with transaction.atomic():
            product = Product.objects.select_for_update().get(id=self.id)
            product.reserved_quantity = models.F("reserved_quantity") - quantity
            product.save(update_fields=["reserved_quantity"])
            return True

    def allocate_stock(self, quantity):
        """Move stock from reserved to allocated."""
        from django.db import transaction

        if not self.track_inventory:
            return True

        with transaction.atomic():
            product = Product.objects.select_for_update().get(id=self.id)
            if product.reserved_quantity >= quantity:
                product.reserved_quantity = models.F("reserved_quantity") - quantity
                product.allocated_quantity = models.F("allocated_quantity") + quantity
                product.save(update_fields=["reserved_quantity", "allocated_quantity"])
                return True
            return False

    def deallocate_stock(self, quantity):
        """Return allocated stock to available."""
        from django.db import transaction

        if not self.track_inventory:
            return True

        with transaction.atomic():
            product = Product.objects.select_for_update().get(id=self.id)
            product.allocated_quantity = models.F("allocated_quantity") - quantity
            product.save(update_fields=["allocated_quantity"])
            return True


class StockReservation(TimeStampedModel):
    """Track stock reservations for order management."""

    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="reservations"
    )
    quantity = models.PositiveIntegerField()
    reason = models.CharField(max_length=255, default="Order reservation")
    expires_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    # Optional order reference
    order_id = models.UUIDField(null=True, blank=True, help_text="Related order ID")

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["product", "is_active"]),
            models.Index(fields=["expires_at"]),
            models.Index(fields=["order_id"]),
        ]

    def __str__(self):
        return f"Reservation: {self.quantity}x {self.product.name}"

    @property
    def is_expired(self):
        """Check if reservation has expired."""
        if not self.expires_at:
            return False
        from django.utils import timezone

        return timezone.now() > self.expires_at

    def extend_expiration(self, minutes=30):
        """Extend reservation expiration."""
        from django.utils import timezone
        from datetime import timedelta

        self.expires_at = timezone.now() + timedelta(minutes=minutes)
        self.save(update_fields=["expires_at"])

    def release(self):
        """Release this reservation."""
        if self.is_active:
            self.product.release_reservation(self.quantity)
            self.is_active = False
            self.save(update_fields=["is_active"])


class StockMovement(TimeStampedModel):
    """Track all stock movements for audit purposes."""

    MOVEMENT_TYPES = [
        ("IN", "Stock In"),
        ("OUT", "Stock Out"),
        ("RESERVE", "Reserved"),
        ("RELEASE", "Released"),
        ("ALLOCATE", "Allocated"),
        ("DEALLOCATE", "Deallocated"),
        ("ADJUSTMENT", "Adjustment"),
    ]

    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="stock_movements"
    )
    movement_type = models.CharField(max_length=10, choices=MOVEMENT_TYPES)
    quantity = models.IntegerField(help_text="Can be negative for outbound movements")
    reason = models.CharField(max_length=255)
    reference_id = models.UUIDField(
        null=True, blank=True, help_text="Reference to order, reservation, etc."
    )

    # Stock levels after this movement
    stock_after = models.PositiveIntegerField()
    reserved_after = models.PositiveIntegerField()
    allocated_after = models.PositiveIntegerField()

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["product", "movement_type"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["reference_id"]),
        ]

    def __str__(self):
        return f"{self.movement_type}: {self.quantity}x {self.product.name}"
