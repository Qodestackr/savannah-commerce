from django.db import models
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django.utils import timezone
from apps.core.models import TimeStampedModel
import json
import uuid

User = get_user_model()


class AuditEvent(TimeStampedModel):
    """
    Comprehensive audit trail for compliance.
    Tracks all system events, data changes, and user actions.
    """

    ACTION_TYPES = [
        # Data Operations
        ("CREATE", "Record Created"),
        ("UPDATE", "Record Updated"),
        ("DELETE", "Record Deleted"),
        ("VIEW", "Record Viewed"),
        # Authentication Events
        ("LOGIN", "User Login"),
        ("LOGOUT", "User Logout"),
        ("LOGIN_FAILED", "Login Failed"),
        ("PASSWORD_CHANGE", "Password Changed"),
        ("PERMISSION_DENIED", "Permission Denied"),
        # Business Operations
        ("ORDER_CREATED", "Order Created"),
        ("ORDER_CONFIRMED", "Order Confirmed"),
        ("ORDER_CANCELLED", "Order Cancelled"),
        ("STOCK_RESERVED", "Stock Reserved"),
        ("STOCK_ALLOCATED", "Stock Allocated"),
        ("INVENTORY_ADJUSTED", "Inventory Adjusted"),
        # System Events
        ("SYSTEM_START", "System Started"),
        ("SYSTEM_STOP", "System Stopped"),
        ("BACKUP_CREATED", "Backup Created"),
        ("MIGRATION_RUN", "Migration Executed"),
        # Security Events
        ("SUSPICIOUS_ACTIVITY", "Suspicious Activity"),
        ("DATA_EXPORT", "Data Exported"),
        ("ADMIN_ACTION", "Administrative Action"),
        ("BULK_OPERATION", "Bulk Operation"),
    ]

    RISK_LEVELS = [
        ("LOW", "Low Risk"),
        ("MEDIUM", "Medium Risk"),
        ("HIGH", "High Risk"),
        ("CRITICAL", "Critical Risk"),
    ]

    # Core audit fields
    event_id = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)
    action_type = models.CharField(max_length=20, choices=ACTION_TYPES, db_index=True)
    risk_level = models.CharField(
        max_length=10, choices=RISK_LEVELS, default="LOW", db_index=True
    )

    # User information
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_events",
    )
    user_email = models.EmailField(
        blank=True, help_text="Stored for historical reference"
    )
    session_key = models.CharField(max_length=40, blank=True, db_index=True)

    # Request context
    ip_address = models.GenericIPAddressField(null=True, blank=True, db_index=True)
    user_agent = models.TextField(blank=True)
    request_method = models.CharField(max_length=10, blank=True)
    request_path = models.CharField(max_length=500, blank=True, db_index=True)

    # Target object information
    content_type = models.ForeignKey(
        ContentType, on_delete=models.SET_NULL, null=True, blank=True
    )
    object_id = models.CharField(max_length=255, blank=True, db_index=True)
    content_object = GenericForeignKey("content_type", "object_id")
    object_repr = models.CharField(
        max_length=500, blank=True, help_text="String representation of object"
    )

    # Event details
    description = models.TextField(help_text="Human-readable description of the event")
    additional_data = models.JSONField(
        default=dict, blank=True, help_text="Additional context data"
    )

    # Data change tracking
    changed_fields = models.JSONField(
        default=list, blank=True, help_text="List of changed field names"
    )
    old_values = models.JSONField(default=dict, blank=True, help_text="Previous values")
    new_values = models.JSONField(default=dict, blank=True, help_text="New values")

    # Compliance fields
    regulation_tags = models.JSONField(
        default=list, blank=True, help_text="Applicable regulations (HIPAA, FDA, etc.)"
    )
    retention_until = models.DateTimeField(
        null=True, blank=True, help_text="When this record can be purged"
    )
    is_sensitive = models.BooleanField(
        default=False, help_text="Contains sensitive data"
    )

    # System context
    process_id = models.CharField(
        max_length=50, blank=True, help_text="System process identifier"
    )
    correlation_id = models.UUIDField(
        null=True, blank=True, db_index=True, help_text="Groups related events"
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["action_type", "created_at"]),
            models.Index(fields=["user", "created_at"]),
            models.Index(fields=["ip_address", "created_at"]),
            models.Index(fields=["risk_level", "created_at"]),
            models.Index(fields=["content_type", "object_id"]),
            models.Index(fields=["correlation_id"]),
            models.Index(fields=["is_sensitive"]),
        ]

        # Compliance requirement
        db_table = "audit_events"

    def __str__(self):
        return (
            f"{self.action_type} by {self.user_email or 'System'} at {self.created_at}"
        )

    @property
    def duration_since_event(self):
        """Calculate time elapsed since event."""
        return timezone.now() - self.created_at

    def mark_as_sensitive(self, regulation_tags=None):
        """Mark event as containing sensitive data."""
        self.is_sensitive = True
        if regulation_tags:
            self.regulation_tags = regulation_tags
        self.save(update_fields=["is_sensitive", "regulation_tags"])

    def add_correlation(self, correlation_id):
        """Add correlation ID to group related events."""
        self.correlation_id = correlation_id
        self.save(update_fields=["correlation_id"])


class DataAccessLog(TimeStampedModel):
    """
    Specific tracking for data access patterns.
    Critical for compliance and security monitoring.
    """

    ACCESS_TYPES = [
        ("READ", "Data Read"),
        ("SEARCH", "Data Search"),
        ("EXPORT", "Data Export"),
        ("BULK_READ", "Bulk Data Access"),
        ("REPORT", "Report Generation"),
    ]

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="data_access_logs"
    )
    access_type = models.CharField(max_length=20, choices=ACCESS_TYPES, db_index=True)

    # What was accessed
    resource_type = models.CharField(
        max_length=100, db_index=True
    )  # 'order', 'product', 'customer', etc.
    resource_ids = models.JSONField(help_text="List of accessed resource IDs")
    record_count = models.PositiveIntegerField(default=1)

    # Context
    ip_address = models.GenericIPAddressField(db_index=True)
    user_agent = models.TextField(blank=True)
    api_endpoint = models.CharField(max_length=255, blank=True)
    query_filters = models.JSONField(
        default=dict, blank=True, help_text="Applied filters/search terms"
    )

    # Security monitoring
    is_suspicious = models.BooleanField(default=False, db_index=True)
    risk_score = models.IntegerField(default=0, help_text="Calculated risk score 0-100")

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "created_at"]),
            models.Index(fields=["resource_type", "created_at"]),
            models.Index(fields=["is_suspicious"]),
            models.Index(fields=["risk_score"]),
        ]

    def __str__(self):
        return f"{self.user.email} accessed {self.record_count} {self.resource_type} records"


class SecurityEvent(TimeStampedModel):
    """
    Security-specific events requiring immediate attention.
    """

    SEVERITY_LEVELS = [
        ("INFO", "Informational"),
        ("WARNING", "Warning"),
        ("ERROR", "Error"),
        ("CRITICAL", "Critical"),
    ]

    EVENT_CATEGORIES = [
        ("AUTH_FAILURE", "Authentication Failure"),
        ("PERMISSION_VIOLATION", "Permission Violation"),
        ("SUSPICIOUS_PATTERN", "Suspicious Activity Pattern"),
        ("DATA_BREACH_ATTEMPT", "Potential Data Breach"),
        ("SYSTEM_COMPROMISE", "System Compromise"),
        ("POLICY_VIOLATION", "Policy Violation"),
    ]

    event_category = models.CharField(
        max_length=30, choices=EVENT_CATEGORIES, db_index=True
    )
    severity = models.CharField(max_length=10, choices=SEVERITY_LEVELS, db_index=True)

    # Event details
    title = models.CharField(max_length=255)
    description = models.TextField()
    raw_data = models.JSONField(
        default=dict, help_text="Raw event data for investigation"
    )

    # Source information
    source_ip = models.GenericIPAddressField(db_index=True)
    user_agent = models.TextField(blank=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    # Response tracking
    is_resolved = models.BooleanField(default=False, db_index=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="resolved_security_events",
    )
    resolution_notes = models.TextField(blank=True)

    # Automated response
    auto_response_taken = models.BooleanField(default=False)
    response_actions = models.JSONField(
        default=list, help_text="Automated actions taken"
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["severity", "is_resolved"]),
            models.Index(fields=["event_category", "created_at"]),
            models.Index(fields=["source_ip", "created_at"]),
        ]

    def __str__(self):
        return f"{self.severity} - {self.title}"

    def resolve(self, user, notes=""):
        """Mark security event as resolved."""
        self.is_resolved = True
        self.resolved_at = timezone.now()
        self.resolved_by = user
        self.resolution_notes = notes
        self.save()


class ComplianceReport(TimeStampedModel):
    """
    Generated compliance reports for regulations.
    """

    REPORT_TYPES = [
        ("HIPAA_ACCESS", "HIPAA Access Report"),
        ("DATA_RETENTION", "Data Retention Report"),
        ("SECURITY_AUDIT", "Security Audit Report"),
        ("USER_ACTIVITY", "User Activity Report"),
        ("SYSTEM_CHANGES", "System Changes Report"),
    ]

    report_type = models.CharField(max_length=20, choices=REPORT_TYPES)
    title = models.CharField(max_length=255)

    # Report parameters
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    generated_by = models.ForeignKey(User, on_delete=models.CASCADE)

    # Report content
    summary = models.JSONField(help_text="Report summary statistics")
    findings = models.JSONField(help_text="Detailed findings")
    recommendations = models.JSONField(default=list, help_text="Recommended actions")

    # File storage
    report_file_path = models.CharField(max_length=500, blank=True)
    file_hash = models.CharField(
        max_length=64, blank=True, help_text="SHA-256 hash for integrity"
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["report_type", "created_at"]),
            models.Index(fields=["generated_by", "created_at"]),
        ]

    def __str__(self):
        return f"{self.title} - {self.created_at.date()}"
