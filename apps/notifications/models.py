from django.contrib.auth import get_user_model
from django.db import models

from apps.core.models import TimeStampedModel

User = get_user_model()


class NotificationTemplate(TimeStampedModel):
    """Email/SMS notification templates."""

    TEMPLATE_TYPES = [
        ("email", "Email"),
        ("sms", "SMS"),
    ]

    name = models.CharField(max_length=255)
    template_type = models.CharField(max_length=10, choices=TEMPLATE_TYPES)
    subject = models.CharField(max_length=255, blank=True, null=True)  # For email only
    content = models.TextField()
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} ({self.template_type})"


class NotificationLog(TimeStampedModel):
    """Log of sent notifications."""

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("sent", "Sent"),
        ("failed", "Failed"),
    ]

    recipient = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="notifications"
    )
    template = models.ForeignKey(NotificationTemplate, on_delete=models.CASCADE)
    recipient_email = models.EmailField(blank=True, null=True)
    recipient_phone = models.CharField(max_length=20, blank=True, null=True)
    content = models.TextField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pending")
    error_message = models.TextField(blank=True, null=True)
    sent_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Notification to {self.recipient.email} - {self.status}"
