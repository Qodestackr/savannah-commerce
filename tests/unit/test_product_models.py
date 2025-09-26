import pytest
from apps.products.models import Category, Product


@pytest.mark.django_db
class TestCategory:
    def test_create_category(self):
        category = Category.objects.create(
            name="Electronics", description="Electronic products"
        )
        assert category.name == "Electronics"
        assert category.slug == "electronics"
        assert str(category) == "Electronics"

    def test_hierarchical_categories(self):
        parent = Category.objects.create(name="Electronics")
        child = Category.objects.create(name="Phones", parent=parent)

        assert child.parent == parent
        assert child in parent.get_children()
        assert child.full_path == "Electronics > Phones"


@pytest.mark.django_db
class TestProduct:
    def test_create_product(self):
        category = Category.objects.create(name="Electronics")
        product = Product.objects.create(
            name="iPhone 15",
            description="Latest iPhone",
            price=999.99,
            sku="IPHONE15-001",
            category=category,
            stock_quantity=10,
        )
        assert product.name == "iPhone 15"
        assert product.price == 999.99
        assert product.is_in_stock is True
        assert product.category == category

    def test_out_of_stock_product(self):
        category = Category.objects.create(name="Electronics")
        product = Product.objects.create(
            name="Old Phone",
            price=100.00,
            sku="OLD-001",
            category=category,
            stock_quantity=0,
        )
        assert product.is_in_stock is False
