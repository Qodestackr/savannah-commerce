from django.contrib.auth import get_user_model

import pytest

from apps.authentication.models import Customer

User = get_user_model()


@pytest.mark.django_db
class TestCustomUser:
    def test_create_user(self):
        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
            first_name="Test",
            last_name="User",
        )
        assert user.email == "test@example.com"
        assert user.full_name == "Test User"
        assert user.check_password("testpass123")

    def test_create_superuser(self):
        admin_user = User.objects.create_superuser(
            username="admin", email="admin@example.com", password="adminpass123"
        )
        assert admin_user.is_staff
        assert admin_user.is_superuser


@pytest.mark.django_db
class TestCustomer:
    def test_create_customer(self):
        user = User.objects.create_user(
            username="customer1", email="customer@example.com", password="pass123"
        )
        customer = Customer.objects.create(
            user=user, phone="+254700000000", address="123 Test Street"
        )
        assert customer.user == user
        assert str(customer) == "Customer: customer@example.com"
