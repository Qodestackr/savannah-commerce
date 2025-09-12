from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Avg
from .models import Category, Product
from .serializers import CategorySerializer, ProductSerializer, CategoryTreeSerializer


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.filter(is_active=True)
    serializer_class = CategorySerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    lookup_field = 'slug'
    
    @action(detail=True, methods=['get'])
    def products(self, request, slug=None):
        category = self.get_object()
        # Get all products in this category and its descendants
        descendant_categories = category.get_descendants(include_self=True)
        products = Product.objects.filter(
            category__in=descendant_categories,
            is_active=True
        )
        serializer = ProductSerializer(products, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'], url_path='avg-price')
    def average_price(self, request, slug=None):
        category = self.get_object()
        # Calculate average price for all products in this category and its descendants
        descendant_categories = category.get_descendants(include_self=True)
        avg_price = Product.objects.filter(
            category__in=descendant_categories,
            is_active=True
        ).aggregate(avg_price=Avg('price'))
        
        return Response({
            'category': category.name,
            'average_price': avg_price['avg_price'] or 0
        })
    
    @action(detail=False, methods=['get'], url_path='tree')
    def tree_view(self, request):
        # Return hierarchical tree structure
        root_categories = Category.objects.filter(parent=None, is_active=True)
        serializer = CategoryTreeSerializer(root_categories, many=True)
        return Response(serializer.data)


class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.filter(is_active=True)
    serializer_class = ProductSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        category_slug = self.request.query_params.get('category', None)
        search = self.request.query_params.get('search', None)
        
        if category_slug:
            try:
                category = Category.objects.get(slug=category_slug)
                descendant_categories = category.get_descendants(include_self=True)
                queryset = queryset.filter(category__in=descendant_categories)
            except Category.DoesNotExist:
                pass
        
        if search:
            queryset = queryset.filter(name__icontains=search)
        
        return queryset