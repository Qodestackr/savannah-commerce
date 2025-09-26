from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import models
from django.db.models import Avg
from django.core.cache import cache
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_headers
from apps.core.permissions import IsOwnerOrReadOnly, CustomerPermission, AdminPermission
from apps.core.throttling import BurstRateThrottle, SustainedRateThrottle, ConditionalThrottle
from .models import Category, Product
from .serializers import CategorySerializer, ProductSerializer, CategoryTreeSerializer
from .filters import ProductFilter, CategoryFilter, AdvancedProductFilter
from django_filters.rest_framework import DjangoFilterBackend


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.filter(is_active=True)
    serializer_class = CategorySerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    throttle_classes = [BurstRateThrottle, SustainedRateThrottle]
    filterset_class = CategoryFilter
    filter_backends = [DjangoFilterBackend]
    lookup_field = 'slug'
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_at', 'level']
    ordering = ['tree_id', 'lft']
    
    def get_permissions(self):
        """
        Instantiate and return the list of permissions that this view requires.
        """
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [AdminPermission]
        else:
            permission_classes = [permissions.IsAuthenticatedOrReadOnly]
        
        return [permission() for permission in permission_classes]
    
    def get_queryset(self):
        """
        Optimize queryset with select_related for better performance.
        """
        queryset = super().get_queryset()
        return queryset.select_related('parent').prefetch_related('children')
    
    @method_decorator(cache_page(60 * 15))  # Cache for 15 minutes
    @method_decorator(vary_on_headers('Authorization'))
    @action(detail=True, methods=['get'])
    def products(self, request, slug=None):
        category = self.get_object()
        # Get all products in this category and its descendants
        descendant_categories = category.get_descendants(include_self=True)
        products = Product.objects.filter(
            category__in=descendant_categories,
            is_active=True
        ).select_related('category').prefetch_related('category__parent')
        
        # Apply product filtering
        product_filter = ProductFilter(request.GET, queryset=products)
        filtered_products = product_filter.qs
        
        # Pagination
        page = self.paginate_queryset(filtered_products)
        if page is not None:
            serializer = ProductSerializer(page, many=True, context={'request': request})
            return self.get_paginated_response(serializer.data)
        
        serializer = ProductSerializer(filtered_products, many=True, context={'request': request})
        return Response(serializer.data)
    
    @method_decorator(cache_page(60 * 30))  # Cache for 30 minutes
    @action(detail=True, methods=['get'], url_path='avg-price')
    def average_price(self, request, slug=None):
        category = self.get_object()
        cache_key = f"avg_price_{category.slug}"
        
        # Try to get from cache first
        avg_price = cache.get(cache_key)
        if avg_price is None:
            # Calculate average price for all products in this category and its descendants
            descendant_categories = category.get_descendants(include_self=True)
            avg_price_result = Product.objects.filter(
                category__in=descendant_categories,
                is_active=True
            ).aggregate(avg_price=Avg('price'))
            
            avg_price = avg_price_result['avg_price'] or 0
            # Cache for 1 hour
            cache.set(cache_key, avg_price, 60 * 60)
        
        return Response({
            'category': category.name,
            'category_path': category.full_path,
            'average_price': round(float(avg_price), 2),
            'descendant_count': category.get_descendant_count(),
        })
    
    @method_decorator(cache_page(60 * 60))  # Cache for 1 hour
    @action(detail=False, methods=['get'], url_path='tree')
    def tree_view(self, request):
        # Return hierarchical tree structure
        cache_key = "category_tree"
        tree_data = cache.get(cache_key)
        
        if tree_data is None:
            root_categories = Category.objects.filter(parent=None, is_active=True)
            serializer = CategoryTreeSerializer(root_categories, many=True)
            tree_data = serializer.data
            # Cache for 1 hour
            cache.set(cache_key, tree_data, 60 * 60)
        
        return Response(tree_data)
    
    @action(detail=True, methods=['get'], url_path='analytics')
    def analytics(self, request, slug=None):
        """
        Get category analytics data.
        """
        category = self.get_object()
        descendant_categories = category.get_descendants(include_self=True)
        
        products = Product.objects.filter(
            category__in=descendant_categories,
            is_active=True
        )
        
        analytics = {
            'total_products': products.count(),
            'total_stock': products.aggregate(total=models.Sum('stock_quantity'))['total'] or 0,
            'avg_price': products.aggregate(avg=Avg('price'))['avg'] or 0,
            'price_range': {
                'min': products.aggregate(min=models.Min('price'))['min'] or 0,
                'max': products.aggregate(max=models.Max('price'))['max'] or 0,
            },
            'stock_status': {
                'in_stock': products.filter(stock_quantity__gt=0).count(),
                'out_of_stock': products.filter(stock_quantity=0).count(),
                'low_stock': products.filter(stock_quantity__lte=10, stock_quantity__gt=0).count(),
            }
        }
        
        return Response(analytics)


class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.filter(is_active=True)
    serializer_class = ProductSerializer
    permission_classes = [IsOwnerOrReadOnly]
    throttle_classes = [BurstRateThrottle, ConditionalThrottle]
    filterset_class = AdvancedProductFilter
    filter_backends = [DjangoFilterBackend]
    search_fields = ['name', 'description', 'sku']
    ordering_fields = ['name', 'price', 'created_at', 'stock_quantity']
    ordering = ['-created_at']
    
    def get_permissions(self):
        """
        Instantiate and return the list of permissions that this view requires.
        """
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [AdminPermission]
        elif self.action in ['list', 'retrieve']:
            permission_classes = [permissions.IsAuthenticatedOrReadOnly]
        else:
            permission_classes = [CustomerPermission]
        
        return [permission() for permission in permission_classes]
    
    def get_queryset(self):
        """
        Optimize queryset with proper relationships and apply user-specific filtering.
        """
        queryset = super().get_queryset()
        queryset = queryset.select_related('category').prefetch_related(
            'category__parent',
            'category__ancestors'
        )
        
        # Additional filtering can be added here based on user permissions
        if not self.request.user.is_staff:
            # Non-admin users only see active products
            queryset = queryset.filter(is_active=True)
        
        return queryset
    
    @action(detail=True, methods=['get'], url_path='similar')
    def similar_products(self, request, pk=None):
        """
        Get similar products based on category and price range.
        """
        product = self.get_object()
        price_range = product.price * 0.2  # 20% price variance
        
        similar = Product.objects.filter(
            category=product.category,
            price__gte=product.price - price_range,
            price__lte=product.price + price_range,
            is_active=True
        ).exclude(id=product.id)[:5]
        
        serializer = self.get_serializer(similar, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'], url_path='trending')
    def trending_products(self, request):
        """
        Get trending products based on recent orders.
        """
        # This would typically involve order data analysis
        # For now, return products with highest stock turnover
        trending = self.get_queryset().filter(
            stock_quantity__gt=0
        ).order_by('-created_at')[:10]
        
        serializer = self.get_serializer(trending, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'], url_path='low-stock')
    def low_stock_products(self, request):
        """
        Get products with low stock for inventory management.
        Admin only.
        """
        if not request.user.is_staff:
            return Response(
                {'error': 'Permission denied'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        low_stock = self.get_queryset().filter(
            stock_quantity__lte=10,
            stock_quantity__gt=0,
            is_active=True
        ).order_by('stock_quantity')
        
        serializer = self.get_serializer(low_stock, many=True)
        return Response(serializer.data)