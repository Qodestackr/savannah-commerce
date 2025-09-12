from rest_framework import serializers
from .models import Category, Product


class CategorySerializer(serializers.ModelSerializer):
    children = serializers.SerializerMethodField()
    full_path = serializers.ReadOnlyField()
    
    class Meta:
        model = Category
        fields = ('id', 'name', 'slug', 'description', 'parent', 'full_path', 'children', 'is_active', 'created_at', 'updated_at')
        read_only_fields = ('slug', 'full_path', 'created_at', 'updated_at')
    
    def get_children(self, obj):
        if obj.get_children():
            return CategorySerializer(obj.get_children(), many=True).data
        return []


class ProductSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    category_path = serializers.CharField(source='category.full_path', read_only=True)
    is_in_stock = serializers.ReadOnlyField()
    
    class Meta:
        model = Product
        fields = ('id', 'name', 'description', 'price', 'sku', 'category', 'category_name', 'category_path', 'stock_quantity', 'is_in_stock', 'is_active', 'created_at', 'updated_at')
        read_only_fields = ('created_at', 'updated_at')


class CategoryTreeSerializer(serializers.ModelSerializer):
    children = serializers.SerializerMethodField()
    
    class Meta:
        model = Category
        fields = ('id', 'name', 'slug', 'description', 'children')
    
    def get_children(self, obj):
        children = obj.get_children()
        return CategoryTreeSerializer(children, many=True).data