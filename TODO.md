Neon + Upstash:
Update your .env file:
```sh
DB_NAME=your-neon-db-name
DB_USER=your-neon-username
DB_PASSWORD=your-neon-password
DB_HOST=your-neon-host.neon.tech
DB_PORT=5432

REDIS_URL=rediss://default:your-upstash-password@your-upstash-host:6380
CELERY_BROKER_URL=rediss://default:your-upstash-password@your-upstash-host:6380
```

Simplified Local Setup:
```sh
# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install requirements
pip install -r requirements.txt

# Run migrations
python manage.py migrate --settings=config.settings.development

# Create superuser
python manage.py createsuperuser --settings=config.settings.development

# Start Django server
python manage.py runserver --settings=config.settings.development

# In another terminal: Start Celery
celery -A config worker -l info
```