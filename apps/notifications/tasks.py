from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from django.db.models import Sum, Count, Avg
from datetime import timedelta, datetime
import africastalking
import csv
import io
import logging
from .models import NotificationLog, NotificationTemplate
from apps.orders.models import Order, OrderItem
from apps.products.models import Product, StockReservation

logger = logging.getLogger(__name__)


@shared_task
def send_order_notification(order_id):
    """Send order confirmation notifications."""
    try:
        order = Order.objects.get(id=order_id)
        
        # Send SMS to customer
        send_sms_notification.delay(order.customer.id, 'order_created', {
            'order_id': order.id,
            'total_amount': order.total_amount,
            'status': order.status
        })
        
        # Send email notification to admin
        send_email_notification.delay(None, 'new_order_admin', {
            'order_id': order.id,
            'customer_email': order.customer.email,
            'total_amount': order.total_amount,
            'status': order.status,
            'item_count': order.item_count
        })
        
    except Order.DoesNotExist:
        logger.error(f"Order {order_id} does not exist")


@shared_task
def send_sms_notification(user_id, template_name, context):
    """Send SMS notification using Africa's Talking."""
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
    """Send email notification."""
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


# ADVANCED INVENTORY MANAGEMENT TASKS

@shared_task
def cleanup_expired_reservations():
    """Clean up expired stock reservations."""
    from apps.orders.services import InventoryService
    
    try:
        inventory_service = InventoryService()
        expired_count = inventory_service.cleanup_expired_reservations()
        
        logger.info(f"Cleaned up {expired_count} expired reservations")
        
        # Send alert if many reservations expired
        if expired_count > 10:
            send_email_notification.delay(
                None, 
                'high_reservation_expiry_alert',
                {'expired_count': expired_count}
            )
        
        return expired_count
        
    except Exception as e:
        logger.error(f"Error during reservation cleanup: {e}")
        return 0


@shared_task
def update_inventory_counts():
    """Recalculate and update inventory counts for consistency."""
    try:
        products = Product.objects.filter(track_inventory=True)
        updated_count = 0
        
        for product in products:
            # Calculate actual reserved quantity from active reservations
            actual_reserved = StockReservation.objects.filter(
                product=product,
                is_active=True
            ).aggregate(total=Sum('quantity'))['total'] or 0
            
            # Update if there's a discrepancy
            if product.reserved_quantity != actual_reserved:
                product.reserved_quantity = actual_reserved
                product.save(update_fields=['reserved_quantity'])
                updated_count += 1
                
                logger.info(
                    f"Updated reserved quantity for {product.name}: "
                    f"{product.reserved_quantity} -> {actual_reserved}"
                )
        
        logger.info(f"Updated inventory counts for {updated_count} products")
        return updated_count
        
    except Exception as e:
        logger.error(f"Error updating inventory counts: {e}")
        return 0


@shared_task
def send_low_stock_alerts():
    """Send alerts for products with low stock."""
    try:
        low_stock_products = Product.objects.filter(
            track_inventory=True,
            is_active=True
        ).annotate(
            available=Sum('stock_quantity') - Sum('reserved_quantity') - Sum('allocated_quantity')
        ).filter(available__lte=models.F('low_stock_threshold'))
        
        if low_stock_products.exists():
            # Prepare alert data
            alert_data = []
            for product in low_stock_products:
                alert_data.append({
                    'name': product.name,
                    'sku': product.sku,
                    'available': product.available_quantity,
                    'threshold': product.low_stock_threshold
                })
            
            # Send email alert to admin
            send_email_notification.delay(
                None,
                'low_stock_alert',
                {
                    'product_count': len(alert_data),
                    'products': alert_data
                }
            )
            
            logger.info(f"Sent low stock alert for {len(alert_data)} products")
            return len(alert_data)
        
        return 0
        
    except Exception as e:
        logger.error(f"Error sending low stock alerts: {e}")
        return 0


# REPORTING TASKS

@shared_task
def generate_daily_sales_report():
    """Generate daily sales report."""
    try:
        today = timezone.now().date()
        yesterday = today - timedelta(days=1)
        
        # Get orders from yesterday
        orders = Order.objects.filter(
            created_at__date=yesterday,
            status__in=['confirmed', 'processing', 'shipped', 'delivered']
        )
        
        # Calculate metrics
        total_orders = orders.count()
        total_revenue = orders.aggregate(Sum('total_amount'))['total_amount__sum'] or 0
        avg_order_value = orders.aggregate(Avg('total_amount'))['total_amount__avg'] or 0
        
        # Top products
        top_products = OrderItem.objects.filter(
            order__created_at__date=yesterday,
            order__status__in=['confirmed', 'processing', 'shipped', 'delivered']
        ).values(
            'product__name', 'product__sku'
        ).annotate(
            total_sold=Sum('quantity'),
            total_revenue=Sum('total_price')
        ).order_by('-total_sold')[:5]
        
        # Generate report
        report_data = {
            'date': yesterday.strftime('%Y-%m-%d'),
            'total_orders': total_orders,
            'total_revenue': float(total_revenue),
            'avg_order_value': float(avg_order_value),
            'top_products': list(top_products)
        }
        
        # Send report via email
        send_email_notification.delay(
            None,
            'daily_sales_report',
            report_data
        )
        
        logger.info(f"Generated daily sales report for {yesterday}")
        return report_data
        
    except Exception as e:
        logger.error(f"Error generating daily sales report: {e}")
        return None


@shared_task
def generate_inventory_report():
    """Generate comprehensive inventory report."""
    try:
        # Get inventory data
        products = Product.objects.filter(is_active=True).select_related('category')
        
        report_data = []
        total_value = 0
        low_stock_count = 0
        
        for product in products:
            product_value = float(product.price * product.available_quantity)
            total_value += product_value
            
            if product.is_low_stock:
                low_stock_count += 1
            
            report_data.append({
                'name': product.name,
                'sku': product.sku,
                'category': product.category.name,
                'total_stock': product.stock_quantity,
                'reserved': product.reserved_quantity,
                'allocated': product.allocated_quantity,
                'available': product.available_quantity,
                'price': float(product.price),
                'value': product_value,
                'is_low_stock': product.is_low_stock
            })
        
        # Create CSV report
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=[
            'name', 'sku', 'category', 'total_stock', 'reserved', 
            'allocated', 'available', 'price', 'value', 'is_low_stock'
        ])
        writer.writeheader()
        writer.writerows(report_data)
        
        # Summary data
        summary = {
            'total_products': len(report_data),
            'total_inventory_value': total_value,
            'low_stock_products': low_stock_count,
            'report_generated_at': timezone.now().isoformat()
        }
        
        # Send summary via email
        send_email_notification.delay(
            None,
            'inventory_report_summary',
            summary
        )
        
        logger.info(f"Generated inventory report for {len(report_data)} products")
        return summary
        
    except Exception as e:
        logger.error(f"Error generating inventory report: {e}")
        return None


# DATA CLEANUP TASKS

@shared_task
def archive_old_orders():
    """Archive orders older than 1 year."""
    try:
        cutoff_date = timezone.now() - timedelta(days=365)
        
        old_orders = Order.objects.filter(
            created_at__lt=cutoff_date,
            status__in=['delivered', 'cancelled']
        )
        
        archived_count = old_orders.count()
        
        if archived_count > 0:
            # In a real system, you'd move these to an archive table
            # For now, we'll just log the count
            logger.info(f"Would archive {archived_count} old orders")
            
            # Send summary
            send_email_notification.delay(
                None,
                'order_archival_summary',
                {'archived_count': archived_count, 'cutoff_date': cutoff_date.date()}
            )
        
        return archived_count
        
    except Exception as e:
        logger.error(f"Error archiving old orders: {e}")
        return 0


@shared_task
def cleanup_notification_logs():
    """Clean up old notification logs."""
    try:
        cutoff_date = timezone.now() - timedelta(days=90)
        
        old_logs = NotificationLog.objects.filter(created_at__lt=cutoff_date)
        deleted_count = old_logs.count()
        old_logs.delete()
        
        logger.info(f"Cleaned up {deleted_count} old notification logs")
        return deleted_count
        
    except Exception as e:
        logger.error(f"Error cleaning up notification logs: {e}")
        return 0


# MONITORING TASKS

@shared_task
def system_health_check():
    """Perform system health checks."""
    try:
        checks = {}
        
        # Database connectivity
        try:
            Order.objects.count()
            checks['database'] = 'OK'
        except Exception as e:
            checks['database'] = f'ERROR: {e}'
        
        # Redis connectivity
        try:
            from django.core.cache import cache
            cache.set('health_check', 'test', 30)
            checks['redis'] = 'OK'
        except Exception as e:
            checks['redis'] = f'ERROR: {e}'
        
        # Low stock check
        low_stock_count = Product.objects.filter(
            available_quantity__lte=models.F('low_stock_threshold'),
            track_inventory=True,
            is_active=True
        ).count()
        checks['low_stock_products'] = low_stock_count
        
        # Expired reservations check
        expired_reservations = StockReservation.objects.filter(
            expires_at__lt=timezone.now(),
            is_active=True
        ).count()
        checks['expired_reservations'] = expired_reservations
        
        logger.info(f"System health check completed: {checks}")
        
        # Send alert if critical issues found
        if checks['database'] != 'OK' or checks['redis'] != 'OK':
            send_email_notification.delay(
                None,
                'system_health_alert',
                checks
            )
        
        return checks
        
    except Exception as e:
        logger.error(f"Error during system health check: {e}")
        return {'error': str(e)}
        # })
        
        # # Send email notification to admin
        # send_email_notification.delay(None, 'new_order_admin', {
        #     'order_id': order.id,
        #     'customer_email': order.customer.email,
        #     'total_amount': order.total_amount
        # })
        
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