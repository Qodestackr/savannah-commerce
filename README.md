# Savannah E-Commerce API Testing Guide

## Overview
This guide provides comprehensive testing instructions for the Savannah E-Commerce backend system built for the Savannah Informatics assessment. The system includes OAuth2 authentication, hierarchical categories, product management, and order processing.

## Prerequisites

### System Requirements
- Python 3.8+
- PostgreSQL (or SQLite for development)
- Redis (for caching and Celery)
- Virtual environment activated

### Environment Setup
```bash
git clone git@github.com:Qodestackr/savannah-commerce.git
cd savannah-commerce

python -m venv venv
source venv/bin/activate 
pip install -r requirements.txt

# Database setup
python manage.py migrate
python manage.py createsuperuser

# Start development server
python manage.py runserver
```

## Authentication Setup

### 1. Create OAuth2 Application

First, create an OAuth2 application through Django admin:

### 2. Get Access Token

```bash
curl -X POST http://127.0.0.1:8000/o/token/ \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=password&username=admin&password=your_password&client_id=your-client-id&client_secret=your-client-secret"
```

**Expected Response:**
```json
{
  "access_token": "O2o8CNEFzwDZheswqBsRCvyqXoUatK",
  "expires_in": 3600,
  "token_type": "Bearer",
  "scope": "read write",
  "refresh_token": "VqzFH1OvrLbprNjYjRDGPEaZ0OzLD2"
}
```

## API Testing Guide

### Environment Variables
Set your access token for convenience:
```bash
export ACCESS_TOKEN="O2o8CNEFzwDZheswqBsRCvyqXoUatK"
```

---

## 1. Category Management

### Create Root Category
```bash
curl -X POST http://127.0.0.1:8000/api/categories/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -d '{
    "name": "Electronics",
    "description": "Electronic devices and accessories"
  }'
```

**Expected Response:**
```json
{
  "id": "ce221d45-376c-462b-8ac4-5b264313e69d",
  "name": "Electronics",
  "slug": "electronics",
  "description": "Electronic devices and accessories",
  "parent": null,
  "full_path": "Electronics",
  "children": [],
  "is_active": true,
  "created_at": "2025-09-26T09:40:54.469600+03:00",
  "updated_at": "2025-09-26T09:40:54.472128+03:00"
}
```

### Create Child Category
```bash
curl -X POST http://127.0.0.1:8000/api/categories/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -d '{
    "name": "Smartphones",
    "description": "Mobile phones and smartphones",
    "parent": "ce221d45-376c-462b-8ac4-5b264313e69d"
  }'
```

### List All Categories
```bash
curl -X GET http://127.0.0.1:8000/api/categories/ \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

### Get Category Tree View
```bash
curl -X GET http://127.0.0.1:8000/api/categories/tree/ \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

### Get Category by Slug
```bash
curl -X GET http://127.0.0.1:8000/api/categories/electronics/ \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

---

## 2. Product Management

### Create Product
```bash
curl -X POST http://127.0.0.1:8000/api/products/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -d '{
    "name": "iPhone 17 Pro Max",
    "description": "Latest Apple smartphone with advanced features",
    "price": 1199.99,
    "sku": "IPHONE-15-PRO-001",
    "category": "ce221d45-376c-462b-8ac4-5b264313e69d",
    "stock_quantity": 50
  }'
```

**Expected Response:**
```json
{
  "id": "bb444022-66be-4bca-9bbb-bea5a96856fd",
  "name": "iPhone 17 Pro Max",
  "description": "Latest Apple smartphone with advanced features",
  "price": "1199.99",
  "sku": "IPHONE-15-PRO-001",
  "category": "ce221d45-376c-462b-8ac4-5b264313e69d",
  "category_name": "Electronics",
  "category_path": "Electronics",
  "stock_quantity": 50,
  "is_in_stock": true,
  "is_active": true,
  "created_at": "2025-09-26T09:42:16.000634+03:00",
  "updated_at": "2025-09-26T09:42:16.001712+03:00"
}
```

### List Products
```bash
curl -X GET http://127.0.0.1:8000/api/products/ \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

### Filter Products by Category
```bash
curl -X GET "http://127.0.0.1:8000/api/products/?category=ce221d45-376c-462b-8ac4-5b264313e69d" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

### Search Products
```bash
curl -X GET "http://127.0.0.1:8000/api/products/?search=iPhone" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

### Get Product Details
```bash
curl -X GET http://127.0.0.1:8000/api/products/bb444022-66be-4bca-9bbb-bea5a96856fd/ \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

---

## 3. Category Analytics

### Get Average Price for Category
```bash
curl -X GET http://127.0.0.1:8000/api/categories/electronics/average_price/ \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

**Expected Response:**
```json
{
  "category": "Electronics",
  "category_path": "Electronics",
  "average_price": 1199.99,
  "descendant_count": 1
}
```

### Get Category Products
```bash
curl -X GET http://127.0.0.1:8000/api/categories/electronics/products/ \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

### Get Category Analytics
```bash
curl -X GET http://127.0.0.1:8000/api/categories/electronics/analytics/ \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

---

## 4. User Management

### Register New Customer
```bash
curl -X POST http://127.0.0.1:8000/api/auth/register/ \
  -H "Content-Type: application/json" \
  -d '{
    "username": "johndoe",
    "email": "john@example.com",
    "password": "securepassword123",
    "first_name": "John",
    "last_name": "Doe",
    "phone": "+254700000000"
  }'
```

### Get User Profile
```bash
curl -X GET http://127.0.0.1:8000/api/auth/profile/ \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

---

## 5. Order Management

### Create Order (Fixed Version)
The order creation requires an `items` field, not `products`. Here's the correct format:

```bash
curl -X POST http://127.0.0.1:8000/api/orders/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -d '{
    "items": [
      {
        "product": "bb444022-66be-4bca-9bbb-bea5a96856fd",
        "quantity": 2
      }
    ]
  }'
```

**Expected Response:**
```json
{
  "id": "order-uuid",
  "customer": "customer-uuid",
  "status": "pending",
  "total_price": "1999.98",
  "items": [
    {
      "product": "bb444022-66be-4bca-9bbb-bea5a96856fd",
      "product_name": "iPhone 17 Pro Max",
      "quantity": 2,
      "unit_price": "1199.99",
      "total_price": "1999.98"
    }
  ],
  "created_at": "2025-09-26T10:30:00.000000+03:00"
}
```

### List User Orders
```bash
curl -X GET http://127.0.0.1:8000/api/orders/ \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

### Get Order Details
```bash
curl -X GET http://127.0.0.1:8000/api/orders/order-uuid/ \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

### Cancel Order
```bash
curl -X POST http://127.0.0.1:8000/api/orders/order-uuid/cancel/ \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

---

## 6. Advanced Product Features

### Get Similar Products
```bash
curl -X GET http://127.0.0.1:8000/api/products/bb444022-66be-4bca-9bbb-bea5a96856fd/similar/ \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

### Get Trending Products
```bash
curl -X GET http://127.0.0.1:8000/api/products/trending/ \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

### Get Low Stock Products (Admin Only)
```bash
curl -X GET http://127.0.0.1:8000/api/products/low-stock/ \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

---

## 7. Error Handling Test Cases

### Test Invalid Category UUID
```bash
curl -X GET http://127.0.0.1:8000/api/categories/invalid-uuid/ \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

### Test Duplicate SKU
```bash
curl -X POST http://127.0.0.1:8000/api/products/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -d '{
    "name": "Another Product",
    "price": 50,
    "sku": "IPHONE-15-PRO-001",
    "category": "ce221d45-376c-462b-8ac4-5b264313e69d",
    "stock_quantity": 10
  }'
```

### Test Unauthorized Access
```bash
curl -X POST http://127.0.0.1:8000/api/categories/ \
  -H "Content-Type: application/json" \
  -d '{"name": "Test Category"}'
```

---

## 8. Performance Testing

### Test Pagination
```bash
curl -X GET "http://127.0.0.1:8000/api/products/?page=1&page_size=5" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

### Test Filtering and Search
```bash
curl -X GET "http://127.0.0.1:8000/api/products/?search=iPhone&min_price=500&max_price=1500" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

### Test Ordering
```bash
curl -X GET "http://127.0.0.1:8000/api/products/?ordering=-price" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

---

## 9. Common Issues and Solutions

### Issue 1: "This field is required" for items in order creation
**Solution:** Use `items` array instead of `products` array in order payload.

### Issue 2: Category filtering not working
**Solution:** Ensure you're using the correct UUID format and the category exists.

### Issue 3: Authentication failures
**Solution:** Check if your access token is valid and not expired. Refresh if needed.

### Issue 4: Permission denied errors
**Solution:** Ensure your user has the correct permissions for the action you're trying to perform.

---

## 10. Testing Checklist

### Basic Functionality ✅
- [ ] Create OAuth2 application
- [ ] Obtain access token
- [ ] Create root category
- [ ] Create child category
- [ ] Create product
- [ ] Calculate average price
- [ ] Create order
- [ ] List orders

### Advanced Features ✅
- [ ] Test hierarchical categories
- [ ] Filter products by category
- [ ] Search products
- [ ] Get category analytics
- [ ] Test similar products
- [ ] Test pagination
- [ ] Test error handling

### Security Testing ✅
- [ ] Test unauthorized access
- [ ] Test token expiration
- [ ] Test permission-based access
- [ ] Test input validation

---

## Conclusion

This testing guide covers all major endpoints and functionalities of the Savannah e-commerce system