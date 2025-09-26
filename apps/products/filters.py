import django_filters
from django.db import models
from django_filters import rest_framework as filters
from .models import Product, Category


class ProductFilter(django_filters.FilterSet):
    """
    Advanced filtering for products with price ranges, category hierarchy, and text search.
    """

    # Price filtering
    price_min = django_filters.NumberFilter(field_name="price", lookup_expr="gte")
    price_max = django_filters.NumberFilter(field_name="price", lookup_expr="lte")
    price_range = django_filters.RangeFilter(field_name="price")

    # Category filtering (includes descendants)
    category = django_filters.ModelChoiceFilter(
        queryset=Category.objects.all(), method="filter_by_category_tree"
    )
    category_slug = django_filters.CharFilter(method="filter_by_category_slug")

    # Stock filtering
    in_stock = django_filters.BooleanFilter(method="filter_in_stock")
    stock_min = django_filters.NumberFilter(
        field_name="stock_quantity", lookup_expr="gte"
    )
    stock_max = django_filters.NumberFilter(
        field_name="stock_quantity", lookup_expr="lte"
    )
    low_stock = django_filters.BooleanFilter(method="filter_low_stock")

    # Text search across multiple fields
    search = django_filters.CharFilter(method="filter_search")

    # Status filtering
    is_active = django_filters.BooleanFilter(field_name="is_active")

    # Date filtering
    created_after = django_filters.DateTimeFilter(
        field_name="created_at", lookup_expr="gte"
    )
    created_before = django_filters.DateTimeFilter(
        field_name="created_at", lookup_expr="lte"
    )
    updated_after = django_filters.DateTimeFilter(
        field_name="updated_at", lookup_expr="gte"
    )

    # SKU filtering
    sku_contains = django_filters.CharFilter(field_name="sku", lookup_expr="icontains")

    class Meta:
        model = Product
        fields = {
            "name": ["exact", "icontains", "istartswith"],
            "sku": ["exact", "icontains"],
            "price": ["exact", "gte", "lte"],
            "stock_quantity": ["exact", "gte", "lte"],
            "is_active": ["exact"],
            "created_at": ["exact", "gte", "lte"],
        }

    def filter_by_category_tree(self, queryset, name, value):
        """
        Filter by category including all descendant categories.
        """
        if value:
            # Get all descendant categories using MPTT
            descendant_categories = value.get_descendants(include_self=True)
            return queryset.filter(category__in=descendant_categories)
        return queryset

    def filter_by_category_slug(self, queryset, name, value):
        """
        Filter by category slug including descendants.
        """
        if value:
            try:
                category = Category.objects.get(slug=value)
                descendant_categories = category.get_descendants(include_self=True)
                return queryset.filter(category__in=descendant_categories)
            except Category.DoesNotExist:
                return queryset.none()
        return queryset

    def filter_in_stock(self, queryset, name, value):
        """
        Filter products that are in stock.
        """
        if value is True:
            return queryset.filter(stock_quantity__gt=0)
        elif value is False:
            return queryset.filter(stock_quantity=0)
        return queryset

    def filter_low_stock(self, queryset, name, value):
        """
        Filter products with low stock (less than 10 items).
        """
        if value is True:
            return queryset.filter(stock_quantity__lt=10, stock_quantity__gt=0)
        return queryset

    def filter_search(self, queryset, name, value):
        """
        Full-text search across product name, description, and SKU.
        """
        if value:
            return queryset.filter(
                models.Q(name__icontains=value)
                | models.Q(description__icontains=value)
                | models.Q(sku__icontains=value)
                | models.Q(category__name__icontains=value)
            ).distinct()
        return queryset


class CategoryFilter(django_filters.FilterSet):
    """
    Advanced filtering for categories.
    """

    # Hierarchy filtering
    parent = django_filters.ModelChoiceFilter(queryset=Category.objects.all())
    level = django_filters.NumberFilter(field_name="level")
    is_root = django_filters.BooleanFilter(method="filter_root_categories")
    has_children = django_filters.BooleanFilter(method="filter_with_children")

    # Text search
    search = django_filters.CharFilter(method="filter_search")

    # Status
    is_active = django_filters.BooleanFilter(field_name="is_active")

    class Meta:
        model = Category
        fields = {
            "name": ["exact", "icontains", "istartswith"],
            "slug": ["exact", "icontains"],
            "is_active": ["exact"],
            "level": ["exact", "gte", "lte"],
        }

    def filter_root_categories(self, queryset, name, value):
        """
        Filter root categories (no parent).
        """
        if value is True:
            return queryset.filter(parent__isnull=True)
        elif value is False:
            return queryset.filter(parent__isnull=False)
        return queryset

    def filter_with_children(self, queryset, name, value):
        """
        Filter categories that have child categories.
        """
        if value is True:
            return queryset.filter(children__isnull=False).distinct()
        elif value is False:
            return queryset.filter(children__isnull=True)
        return queryset

    def filter_search(self, queryset, name, value):
        """
        Search across category name and description.
        """
        if value:
            return queryset.filter(
                models.Q(name__icontains=value) | models.Q(description__icontains=value)
            ).distinct()
        return queryset


class PriceRangeFilter(django_filters.FilterSet):
    """
    Specialized filter for price range queries with predefined ranges.
    """

    PRICE_CHOICES = [
        ("under_10", "Under $10"),
        ("10_50", "$10 - $50"),
        ("50_100", "$50 - $100"),
        ("100_500", "$100 - $500"),
        ("over_500", "Over $500"),
    ]

    price_range = django_filters.ChoiceFilter(
        choices=PRICE_CHOICES, method="filter_by_price_range"
    )

    class Meta:
        model = Product
        fields = ["price_range"]

    def filter_by_price_range(self, queryset, name, value):
        """
        Filter by predefined price ranges.
        """
        price_ranges = {
            "under_10": (0, 10),
            "10_50": (10, 50),
            "50_100": (50, 100),
            "100_500": (100, 500),
            "over_500": (500, float("inf")),
        }

        if value in price_ranges:
            min_price, max_price = price_ranges[value]
            if max_price == float("inf"):
                return queryset.filter(price__gte=min_price)
            else:
                return queryset.filter(price__gte=min_price, price__lte=max_price)

        return queryset


class AdvancedProductFilter(ProductFilter):
    """
    Extended product filter with additional advanced features.
    """

    # Advanced stock filtering
    available_quantity = django_filters.NumberFilter(method="filter_available_quantity")
    reserved_quantity = django_filters.NumberFilter(method="filter_reserved_quantity")

    # Sorting options
    sort_by = django_filters.ChoiceFilter(
        choices=[
            ("name", "Name A-Z"),
            ("-name", "Name Z-A"),
            ("price", "Price Low-High"),
            ("-price", "Price High-Low"),
            ("created_at", "Oldest First"),
            ("-created_at", "Newest First"),
            ("stock_quantity", "Stock Low-High"),
            ("-stock_quantity", "Stock High-Low"),
        ],
        method="filter_sort_by",
    )

    def filter_available_quantity(self, queryset, name, value):
        """
        Filter by available quantity (stock - reserved).
        """
        if hasattr(Product, "available_quantity"):
            return queryset.filter(available_quantity__gte=value)
        return queryset.filter(stock_quantity__gte=value)

    def filter_reserved_quantity(self, queryset, name, value):
        """
        Filter by reserved quantity.
        """
        if hasattr(Product, "reserved_quantity"):
            return queryset.filter(reserved_quantity__gte=value)
        return queryset

    def filter_sort_by(self, queryset, name, value):
        """
        Sort products by specified criteria.
        """
        if value:
            return queryset.order_by(value)
        return queryset
