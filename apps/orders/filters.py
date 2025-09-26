import django_filters
from django.db import models
from django_filters import rest_framework as filters
from .models import Order, OrderItem
from django.contrib.auth import get_user_model

User = get_user_model()


class OrderFilter(django_filters.FilterSet):
    """
    Advanced filtering for orders with date ranges, status, and amount filtering.
    """
    
    # Status filtering
    status = django_filters.ChoiceFilter(choices=Order.STATUS_CHOICES)
    status_in = django_filters.MultipleChoiceFilter(
        field_name='status',
        choices=Order.STATUS_CHOICES,
        conjoined=False
    )
    
    # Amount filtering
    total_min = django_filters.NumberFilter(field_name='total_amount', lookup_expr='gte')
    total_max = django_filters.NumberFilter(field_name='total_amount', lookup_expr='lte')
    total_range = django_filters.RangeFilter(field_name='total_amount')
    
    # Date filtering
    created_after = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')
    created_before = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='lte')
    created_date = django_filters.DateFilter(field_name='created_at', lookup_expr='date')
    created_date_range = django_filters.DateRangeFilter(field_name='created_at')
    
    # Customer filtering (for admin use)
    customer_email = django_filters.CharFilter(field_name='customer__email', lookup_expr='icontains')
    customer_name = django_filters.CharFilter(method='filter_customer_name')
    
    # Item count filtering
    item_count_min = django_filters.NumberFilter(method='filter_item_count_min')
    item_count_max = django_filters.NumberFilter(method='filter_item_count_max')
    
    # Product filtering (orders containing specific products)
    contains_product = django_filters.NumberFilter(method='filter_contains_product')
    product_sku = django_filters.CharFilter(method='filter_product_sku')
    
    # Search functionality
    search = django_filters.CharFilter(method='filter_search')
    
    class Meta:
        model = Order
        fields = {
            'total_amount': ['exact', 'gte', 'lte'],
            'status': ['exact'],
            'created_at': ['exact', 'gte', 'lte', 'date'],
        }
    
    def filter_customer_name(self, queryset, name, value):
        """
        Filter by customer first name or last name.
        """
        if value:
            return queryset.filter(
                models.Q(customer__first_name__icontains=value) |
                models.Q(customer__last_name__icontains=value)
            )
        return queryset
    
    def filter_item_count_min(self, queryset, name, value):
        """
        Filter orders with minimum number of items.
        """
        if value:
            return queryset.annotate(
                item_count=models.Count('items')
            ).filter(item_count__gte=value)
        return queryset
    
    def filter_item_count_max(self, queryset, name, value):
        """
        Filter orders with maximum number of items.
        """
        if value:
            return queryset.annotate(
                item_count=models.Count('items')
            ).filter(item_count__lte=value)
        return queryset
    
    def filter_contains_product(self, queryset, name, value):
        """
        Filter orders that contain a specific product ID.
        """
        if value:
            return queryset.filter(items__product_id=value).distinct()
        return queryset
    
    def filter_product_sku(self, queryset, name, value):
        """
        Filter orders that contain products with specific SKU.
        """
        if value:
            return queryset.filter(items__product__sku__icontains=value).distinct()
        return queryset
    
    def filter_search(self, queryset, name, value):
        """
        General search across order details.
        """
        if value:
            return queryset.filter(
                models.Q(customer__email__icontains=value) |
                models.Q(customer__first_name__icontains=value) |
                models.Q(customer__last_name__icontains=value) |
                models.Q(shipping_address__icontains=value) |
                models.Q(notes__icontains=value) |
                models.Q(items__product__name__icontains=value) |
                models.Q(items__product__sku__icontains=value)
            ).distinct()
        return queryset


class OrderItemFilter(django_filters.FilterSet):
    """
    Filtering for order items.
    """
    
    # Order filtering
    order_id = django_filters.NumberFilter(field_name='order__id')
    order_status = django_filters.ChoiceFilter(
        field_name='order__status',
        choices=Order.STATUS_CHOICES
    )
    
    # Product filtering
    product_name = django_filters.CharFilter(field_name='product__name', lookup_expr='icontains')
    product_sku = django_filters.CharFilter(field_name='product__sku', lookup_expr='icontains')
    
    # Quantity filtering
    quantity_min = django_filters.NumberFilter(field_name='quantity', lookup_expr='gte')
    quantity_max = django_filters.NumberFilter(field_name='quantity', lookup_expr='lte')
    
    # Price filtering
    unit_price_min = django_filters.NumberFilter(field_name='unit_price', lookup_expr='gte')
    unit_price_max = django_filters.NumberFilter(field_name='unit_price', lookup_expr='lte')
    total_price_min = django_filters.NumberFilter(field_name='total_price', lookup_expr='gte')
    total_price_max = django_filters.NumberFilter(field_name='total_price', lookup_expr='lte')
    
    class Meta:
        model = OrderItem
        fields = {
            'quantity': ['exact', 'gte', 'lte'],
            'unit_price': ['exact', 'gte', 'lte'],
            'total_price': ['exact', 'gte', 'lte'],
        }


class CustomerOrderFilter(OrderFilter):
    """
    Specialized filter for customer's own orders (security-focused).
    """
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
    
    @property
    def qs(self):
        """
        Override to filter only user's own orders.
        """
        queryset = super().qs
        if self.user and self.user.is_authenticated:
            if not self.user.is_staff:
                queryset = queryset.filter(customer=self.user)
        return queryset


class DateRangeOrderFilter(django_filters.FilterSet):
    """
    Specialized filter for date-based order analytics.
    """
    
    # Predefined date ranges
    date_range = django_filters.ChoiceFilter(
        choices=[
            ('today', 'Today'),
            ('yesterday', 'Yesterday'),
            ('this_week', 'This Week'),
            ('last_week', 'Last Week'),
            ('this_month', 'This Month'),
            ('last_month', 'Last Month'),
            ('this_year', 'This Year'),
            ('last_year', 'Last Year'),
        ],
        method='filter_date_range'
    )
    
    class Meta:
        model = Order
        fields = ['date_range']
    
    def filter_date_range(self, queryset, name, value):
        """
        Filter by predefined date ranges.
        """
        from django.utils import timezone
        from datetime import datetime, timedelta
        
        now = timezone.now()
        today = now.date()
        
        if value == 'today':
            return queryset.filter(created_at__date=today)
        elif value == 'yesterday':
            yesterday = today - timedelta(days=1)
            return queryset.filter(created_at__date=yesterday)
        elif value == 'this_week':
            start_week = today - timedelta(days=today.weekday())
            return queryset.filter(created_at__date__gte=start_week)
        elif value == 'last_week':
            start_last_week = today - timedelta(days=today.weekday() + 7)
            end_last_week = start_last_week + timedelta(days=6)
            return queryset.filter(
                created_at__date__gte=start_last_week,
                created_at__date__lte=end_last_week
            )
        elif value == 'this_month':
            start_month = today.replace(day=1)
            return queryset.filter(created_at__date__gte=start_month)
        elif value == 'last_month':
            if today.month == 1:
                start_last_month = today.replace(year=today.year-1, month=12, day=1)
            else:
                start_last_month = today.replace(month=today.month-1, day=1)
            
            end_last_month = today.replace(day=1) - timedelta(days=1)
            return queryset.filter(
                created_at__date__gte=start_last_month,
                created_at__date__lte=end_last_month
            )
        elif value == 'this_year':
            start_year = today.replace(month=1, day=1)
            return queryset.filter(created_at__date__gte=start_year)
        elif value == 'last_year':
            start_last_year = today.replace(year=today.year-1, month=1, day=1)
            end_last_year = today.replace(year=today.year-1, month=12, day=31)
            return queryset.filter(
                created_at__date__gte=start_last_year,
                created_at__date__lte=end_last_year
            )
        
        return queryset