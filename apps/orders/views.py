from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.notifications.tasks import send_order_notification

from .models import Order, OrderItem
from .serializers import OrderCreateSerializer, OrderSerializer


class OrderViewSet(viewsets.ModelViewSet):
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Order.objects.filter(customer=self.request.user)

    def get_serializer_class(self):
        if self.action == "create":
            return OrderCreateSerializer
        return OrderSerializer

    def perform_create(self, serializer):
        order = serializer.save()
        # Trigger notification task
        send_order_notification.delay(order.id)
        return order

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        order = self.get_object()
        if order.status in ["pending", "confirmed"]:
            order.status = "cancelled"
            order.save()
            return Response({"message": "Order cancelled successfully"})
        return Response(
            {"error": "Order cannot be cancelled"}, status=status.HTTP_400_BAD_REQUEST
        )
