from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
import africastalking
from .models import NotificationLog, NotificationTemplate
from apps.orders.models import Order
import logging

logger = logging.getLogger(__name__)


@shared_task
def send_order_notification(order_id):
    try:
        order = Order.objects.get(id=order_id)
        
        # Send SMS to customer
        send_sms_notification.delay(order.customer.id, 'order_created', {
            'order_id': order.id,
            'total_amount': order.total_amount
        })
        
        # Send email notification to admin
        send_email_notification.delay(None, 'new_order_admin', {
            'order_id': order.id,
            'customer_email': order.customer.email,
            'total_amount': order.total_amount
        })
        
    except Order.DoesNotExist:
        logger.error(f"Order {order_id} does not exist")


@shared_task
def send_sms_notification(user_id, template_name, context):
    try:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        user = User.objects.get(id=user_id)
        template = NotificationTemplate.objects.get(
            name=template_name, 
            template_type='sms',
            is_active=True
        )
        
        # Format message with context
        message = template.content.format(**context)
        
        # Initialize Africa's Talking
        africastalking.initialize(
            settings.AFRICASTALKING_USERNAME,
            settings.AFRICASTALKING_API_KEY
        )
        sms = africastalking.SMS
        
        # Get phone number
        phone = getattr(user, 'phone', None)
        if phone:
            response = sms.send(message, [phone])
            
            # Log notification
            NotificationLog.objects.create(
                recipient=user,
                template=template,
                recipient_phone=phone,
                content=message,
                status='sent'
            )
            logger.info(f"SMS sent to {phone}: {response}")
        else:
            logger.warning(f"No phone number for user {user_id}")
            
    except Exception as e:
        logger.error(f"Failed to send SMS: {str(e)}")
        # Log failed notification
        NotificationLog.objects.create(
            recipient_id=user_id,
            template_id=template.id if 'template' in locals() else None,
            content=message if 'message' in locals() else '',
            status='failed',
            error_message=str(e)
        )


@shared_task
def send_email_notification(user_id, template_name, context):
    try:
        template = NotificationTemplate.objects.get(
            name=template_name,
            template_type='email',
            is_active=True
        )
        
        # Format content with context
        subject = template.subject.format(**context) if template.subject else 'Notification'
        message = template.content.format(**context)
        
        if user_id:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            user = User.objects.get(id=user_id)
            recipient_email = user.email
        else:
            # Send to admin
            recipient_email = settings.EMAIL_HOST_USER
        
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[recipient_email],
            fail_silently=False
        )
        
        # Log notification
        NotificationLog.objects.create(
            recipient_id=user_id,
            template=template,
            recipient_email=recipient_email,
            content=message,
            status='sent'
        )
        logger.info(f"Email sent to {recipient_email}")
        
    except Exception as e:
        logger.error(f"Failed to send email: {str(e)}")
        # Log failed notification
        NotificationLog.objects.create(
            recipient_id=user_id,
            template_id=template.id if 'template' in locals() else None,
            content=message if 'message' in locals() else '',
            status='failed',
            error_message=str(e)
        )