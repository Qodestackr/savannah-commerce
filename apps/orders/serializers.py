from rest_framework import serializers
from .models import Order, OrderItem
from apps.products.serializers import ProductSerializer


class OrderItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_sku = serializers.CharField(source="product.sku", read_only=True)

    class Meta:
        model = OrderItem
        fields = (
            "id",
            "product",
            "product_name",
            "product_sku",
            "quantity",
            "unit_price",
            "total_price",
        )
        read_only_fields = ("total_price",)


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True)
    customer_email = serializers.CharField(source="customer.email", read_only=True)
    customer_name = serializers.CharField(source="customer.full_name", read_only=True)
    item_count = serializers.ReadOnlyField()

    class Meta:
        model = Order
        fields = (
            "id",
            "customer",
            "customer_email",
            "customer_name",
            "total_amount",
            "status",
            "shipping_address",
            "notes",
            "items",
            "item_count",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("customer", "created_at", "updated_at")

    def create(self, validated_data):
        items_data = validated_data.pop("items")
        order = Order.objects.create(**validated_data)

        for item_data in items_data:
            OrderItem.objects.create(order=order, **item_data)

        return order


class OrderCreateSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True)

    class Meta:
        model = Order
        fields = ("shipping_address", "notes", "items")

    def validate_items(self, value):
        if not value:
            raise serializers.ValidationError("Order must contain at least one item.")
        return value

    def create(self, validated_data):
        items_data = validated_data.pop("items")
        request = self.context.get("request")

        total_amount = sum(item["quantity"] * item["unit_price"] for item in items_data)

        order = Order.objects.create(
            customer=request.user, total_amount=total_amount, **validated_data
        )

        for item_data in items_data:
            OrderItem.objects.create(order=order, **item_data)

        return order
