# Savannah Informatics E-Commerce Backend

A comprehensive Django REST API for e-commerce operations featuring hierarchical product categories, OAuth2 authentication, order management, and automated SMS/email notifications.

## 🚀 Features

### Core Functionality
- **OAuth2 Authentication**: OpenID Connect integration with secure token-based authentication
- **Hierarchical Categories**: Unlimited depth product categories using MPTT (Modified Preorder Tree Traversal)
- **Product Management**: Full CRUD operations with category-based filtering and search
- **Order Management**: Complete order lifecycle with automated status tracking
- **Real-time Notifications**: SMS via Africa's Talking API and email notifications
- **Async Processing**: Celery-based background tasks for scalable operations

### Technical Highlights
- **RESTful API Design**: Well-structured endpoints with proper HTTP status codes
- **Database Optimization**: Efficient queries for hierarchical data with caching
- **Comprehensive Testing**: 90%+ test coverage with unit and integration tests
- **Docker Containerization**: Production-ready deployment configuration
- **CI/CD Pipeline**: Automated testing and deployment with GitHub Actions
- **API Documentation**: OpenAPI/Swagger integration with interactive docs

## 🛠 Tech Stack

- **Backend**: Python 3.11 + Django 4.2 + Django REST Framework 3.14
- **Database**: PostgreSQL 15 with Redis for caching and Celery
- **Authentication**: django-oauth-toolkit for OpenID Connect
- **Background Tasks**: Celery + Redis for async processing
- **Notifications**: Africa's Talking SMS + Django email backend
- **Testing**: pytest + pytest-django with 90%+ coverage
- **Containerization**: Docker + docker-compose
- **API Documentation**: OpenAPI/Swagger

## 📁 Project Structure

```
savannah-ecommerce/
├── apps/
│   ├── authentication/     # User management and OAuth2
│   ├── products/          # Categories and products with MPTT
│   ├── orders/            # Order management system
│   ├── notifications/     # SMS/Email notification system
│   └── core/              # Shared models and utilities
├── config/
│   ├── settings/          # Environment-specific configurations
│   ├── urls.py           # Main URL configuration
│   ├── wsgi.py           # WSGI application
│   └── celery.py         # Celery configuration
├── tests/
│   ├── unit/             # Unit tests for models and services
│   ├── integration/      # API endpoint tests
│   └── fixtures/         # Test data
├── docs/                 # API documentation
├── docker-compose.yml    # Development environment
├── Dockerfile           # Production container
├── requirements.txt     # Python dependencies
└── pytest.ini          # Test configuration
```

## 🚀 Quick Start

### Prerequisites
- Docker and Docker Compose
- Python 3.11+ (for local development)
- Git

### 1. Clone the Repository
```bash
git clone <repository-url>
cd savannah-ecommerce
```

### 2. Environment Setup
```bash
# Copy environment variables
cp .env.example .env

# Edit .env file with your configurations
# - Database credentials
# - Redis connection
# - Africa's Talking API keys
# - Email configuration
```

### 3. Development with Docker
```bash
# Start all services
docker-compose up -d

# Run migrations
docker-compose exec web python manage.py migrate

# Create superuser
docker-compose exec web python manage.py createsuperuser

# Load sample data (optional)
docker-compose exec web python manage.py loaddata fixtures/sample_data.json
```

### 4. Verify Installation
- API Root: http://localhost:8000/api/
- Admin Panel: http://localhost:8000/admin/
- API Documentation: http://localhost:8000/api/docs/

## 📚 API Endpoints

### Authentication
```http
POST /o/token/                    # OAuth2 token (login)
POST /api/auth/register/          # User registration
GET  /api/auth/profile/           # User profile
GET  /api/auth/customer/          # Customer profile
```

### Products & Categories
```http
GET    /api/categories/                    # List categories
POST   /api/categories/                    # Create category
GET    /api/categories/tree/               # Hierarchical tree view
GET    /api/categories/{slug}/             # Category details
GET    /api/categories/{slug}/products/    # Products in category
GET    /api/categories/{slug}/avg-price/   # Average price by category

GET    /api/products/                      # List products
POST   /api/products/                      # Create product
GET    /api/products/{id}/                 # Product details
PUT    /api/products/{id}/                 # Update product
DELETE /api/products/{id}/                 # Delete product
```

### Orders
```http
GET    /api/orders/                        # List user orders
POST   /api/orders/                        # Create order
GET    /api/orders/{id}/                   # Order details
POST   /api/orders/{id}/cancel/           # Cancel order
```

## 🔐 Authentication

The API uses OAuth2 with OpenID Connect for authentication. Here's how to authenticate:

### 1. Get Access Token
```bash
curl -X POST http://localhost:8000/o/token/ \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=password&username=your_email&password=your_password&client_id=your_client_id&client_secret=your_client_secret"
```

### 2. Use Token in Requests
```bash
curl -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  http://localhost:8000/api/products/
```

## 🔄 Background Tasks

The system uses Celery for background processing:

- **Order Notifications**: Automatic SMS to customers and email to admin
- **Email Processing**: Async email sending to prevent blocking
- **Data Sync**: Scheduled tasks for data synchronization

### Monitor Celery Tasks
```bash
# Start Celery worker
docker-compose exec celery celery -A config worker -l info

# Monitor tasks
docker-compose exec celery celery -A config flower
```

## 🧪 Testing

### Run Tests
```bash
# All tests
docker-compose exec web pytest

# With coverage
docker-compose exec web pytest --cov=apps --cov-report=html

# Specific test file
docker-compose exec web pytest tests/unit/test_product_models.py
```

### Test Coverage
The project maintains 90%+ test coverage with:
- Unit tests for models and business logic
- Integration tests for API endpoints
- Mock tests for external services
- Factory-based test data generation

## 📊 Database Schema

### Key Models
- **CustomUser**: Extended user model with OAuth2 support
- **Customer**: Customer profile linked to user
- **Category**: Hierarchical categories using MPTT
- **Product**: Products with category relationships
- **Order/OrderItem**: Complete order management
- **NotificationLog**: Audit trail for sent notifications

### Key Relationships
```
User (1:1) Customer
Category (1:many) Category (hierarchical)
Category (1:many) Product
User (1:many) Order
Order (1:many) OrderItem
Product (1:many) OrderItem
```

## 🚀 Deployment

### Production Deployment
```bash
# Build production image
docker build -t savannah-ecommerce:latest .

# Deploy with production settings
docker-compose -f docker-compose.prod.yml up -d
```

### Environment Variables
```env
# Required Production Variables
SECRET_KEY=your-secret-key
DEBUG=False
ALLOWED_HOSTS=your-domain.com
DATABASE_URL=postgresql://user:pass@host:port/db
REDIS_URL=redis://host:port/0
AFRICASTALKING_API_KEY=your-api-key
EMAIL_HOST_USER=your-email
EMAIL_HOST_PASSWORD=your-password
```

## 📈 Performance Features

- **Database Optimization**: Optimized queries with select_related/prefetch_related
- **Caching**: Redis-based caching for categories and frequent queries
- **API Pagination**: Efficient pagination for large datasets
- **Background Processing**: Non-blocking operations with Celery
- **Connection Pooling**: Database connection optimization

## 🔧 Development

### Local Development Setup
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\\Scripts\\activate

# Install dependencies
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Start development server
python manage.py runserver
```

### Code Quality
```bash
# Format code
black .

# Sort imports
isort .

# Lint code
flake8

# Type checking
mypy .
```

## 📖 API Documentation

Interactive API documentation is available at:
- **Swagger UI**: http://localhost:8000/api/docs/
- **ReDoc**: http://localhost:8000/api/redoc/
- **OpenAPI Schema**: http://localhost:8000/api/schema/

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

For support and questions:
- Create an issue in the repository
- Check the API documentation
- Review the test cases for usage examples

---

Built with ❤️ for Savannah Informatics Technical Assessment