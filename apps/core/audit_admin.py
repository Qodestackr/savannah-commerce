"""
Admin interface for audit trail management.
Provides comprehensive monitoring and compliance reporting tools.
"""

import json

from django.contrib import admin
from django.db.models import Count, Q
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html

from .audit import AuditEvent, ComplianceReport, DataAccessLog, SecurityEvent


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    """Admin interface for audit events with advanced filtering and search."""

    list_display = [
        "event_id_short",
        "action_type",
        "risk_level",
        "user_email",
        "target_object",
        "created_at",
        "is_sensitive",
        "regulation_tags_display",
    ]
    list_filter = [
        "action_type",
        "risk_level",
        "is_sensitive",
        "created_at",
        ("content_type", admin.RelatedOnlyFieldListFilter),
        ("user", admin.RelatedOnlyFieldListFilter),
    ]
    search_fields = [
        "user_email",
        "description",
        "object_repr",
        "ip_address",
        "request_path",
    ]
    readonly_fields = [
        "event_id",
        "created_at",
        "updated_at",
        "correlation_id",
        "duration_since_event",
        "additional_data_formatted",
    ]
    date_hierarchy = "created_at"
    ordering = ["-created_at"]

    fieldsets = (
        (
            "Event Information",
            {
                "fields": (
                    "event_id",
                    "action_type",
                    "risk_level",
                    "description",
                    "created_at",
                    "duration_since_event",
                )
            },
        ),
        (
            "User Context",
            {
                "fields": (
                    "user",
                    "user_email",
                    "session_key",
                    "ip_address",
                    "user_agent",
                    "request_method",
                    "request_path",
                )
            },
        ),
        ("Target Object", {"fields": ("content_type", "object_id", "object_repr")}),
        (
            "Data Changes",
            {
                "fields": ("changed_fields", "old_values", "new_values"),
                "classes": ("collapse",),
            },
        ),
        (
            "Compliance",
            {"fields": ("regulation_tags", "retention_until", "is_sensitive")},
        ),
        (
            "System Context",
            {
                "fields": ("process_id", "correlation_id", "additional_data_formatted"),
                "classes": ("collapse",),
            },
        ),
    )

    def event_id_short(self, obj):
        """Display shortened event ID."""
        return str(obj.event_id)[:8] + "..."

    event_id_short.short_description = "Event ID"

    def target_object(self, obj):
        """Display target object with link if available."""
        if obj.content_object:
            try:
                admin_url = reverse(
                    f"admin:{obj.content_type.app_label}_{obj.content_type.model}_change",
                    args=[obj.object_id],
                )
                return format_html('<a href="{}">{}</a>', admin_url, obj.object_repr)
            except:
                return obj.object_repr
        return obj.object_repr or "-"

    target_object.short_description = "Target Object"

    def regulation_tags_display(self, obj):
        """Display regulation tags as badges."""
        if not obj.regulation_tags:
            return "-"

        badges = []
        for tag in obj.regulation_tags:
            color = {
                "HIPAA": "#e74c3c",
                "FDA_21CFR11": "#3498db",
                "SOX": "#f39c12",
                "GDPR": "#2ecc71",
                "ISO_13485": "#9b59b6",
            }.get(tag, "#95a5a6")

            badges.append(
                f'<span style="background-color: {color}; color: white; '
                f"padding: 2px 6px; border-radius: 3px; font-size: 11px; "
                f'margin-right: 2px;">{tag}</span>'
            )

        return format_html("".join(badges))

    regulation_tags_display.short_description = "Regulations"

    def additional_data_formatted(self, obj):
        """Format additional data as readable JSON."""
        if not obj.additional_data:
            return "-"
        return format_html("<pre>{}</pre>", json.dumps(obj.additional_data, indent=2))

    additional_data_formatted.short_description = "Additional Data"

    def duration_since_event(self, obj):
        """Show time elapsed since event."""
        return obj.duration_since_event

    duration_since_event.short_description = "Time Elapsed"

    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        return super().get_queryset(request).select_related("user", "content_type")


@admin.register(DataAccessLog)
class DataAccessLogAdmin(admin.ModelAdmin):
    """Admin interface for data access logs."""

    list_display = [
        "user",
        "access_type",
        "resource_type",
        "record_count",
        "created_at",
        "is_suspicious",
        "risk_score",
    ]
    list_filter = [
        "access_type",
        "resource_type",
        "is_suspicious",
        "created_at",
        ("user", admin.RelatedOnlyFieldListFilter),
    ]
    search_fields = ["user__email", "resource_type", "api_endpoint", "ip_address"]
    readonly_fields = ["created_at", "updated_at", "query_filters_formatted"]
    date_hierarchy = "created_at"
    ordering = ["-created_at"]

    fieldsets = (
        (
            "Access Information",
            {
                "fields": (
                    "user",
                    "access_type",
                    "resource_type",
                    "record_count",
                    "created_at",
                )
            },
        ),
        (
            "Request Context",
            {
                "fields": (
                    "ip_address",
                    "user_agent",
                    "api_endpoint",
                    "query_filters_formatted",
                )
            },
        ),
        ("Security Assessment", {"fields": ("is_suspicious", "risk_score")}),
    )

    def query_filters_formatted(self, obj):
        """Format query filters as readable JSON."""
        if not obj.query_filters:
            return "-"
        return format_html("<pre>{}</pre>", json.dumps(obj.query_filters, indent=2))

    query_filters_formatted.short_description = "Query Filters"


@admin.register(SecurityEvent)
class SecurityEventAdmin(admin.ModelAdmin):
    """Admin interface for security events with incident response tracking."""

    list_display = [
        "title",
        "event_category",
        "severity",
        "source_ip",
        "user",
        "created_at",
        "is_resolved",
        "resolved_by",
    ]
    list_filter = [
        "event_category",
        "severity",
        "is_resolved",
        "created_at",
        ("user", admin.RelatedOnlyFieldListFilter),
        ("resolved_by", admin.RelatedOnlyFieldListFilter),
    ]
    search_fields = ["title", "description", "source_ip", "user__email"]
    readonly_fields = [
        "created_at",
        "updated_at",
        "raw_data_formatted",
        "response_actions_formatted",
    ]
    date_hierarchy = "created_at"
    ordering = ["-created_at"]

    fieldsets = (
        (
            "Event Information",
            {
                "fields": (
                    "title",
                    "event_category",
                    "severity",
                    "description",
                    "created_at",
                )
            },
        ),
        ("Source Information", {"fields": ("source_ip", "user_agent", "user")}),
        (
            "Resolution",
            {
                "fields": (
                    "is_resolved",
                    "resolved_at",
                    "resolved_by",
                    "resolution_notes",
                )
            },
        ),
        (
            "Automated Response",
            {
                "fields": ("auto_response_taken", "response_actions_formatted"),
                "classes": ("collapse",),
            },
        ),
        ("Raw Data", {"fields": ("raw_data_formatted",), "classes": ("collapse",)}),
    )

    actions = ["mark_resolved", "mark_unresolved"]

    def mark_resolved(self, request, queryset):
        """Bulk action to mark events as resolved."""
        count = 0
        for event in queryset.filter(is_resolved=False):
            event.resolve(request.user, "Bulk resolution via admin")
            count += 1

        self.message_user(request, f"Successfully resolved {count} security events.")

    mark_resolved.short_description = "Mark selected events as resolved"

    def mark_unresolved(self, request, queryset):
        """Bulk action to mark events as unresolved."""
        count = queryset.filter(is_resolved=True).update(
            is_resolved=False, resolved_at=None, resolved_by=None, resolution_notes=""
        )

        self.message_user(
            request, f"Successfully marked {count} security events as unresolved."
        )

    mark_unresolved.short_description = "Mark selected events as unresolved"

    def raw_data_formatted(self, obj):
        """Format raw data as readable JSON."""
        if not obj.raw_data:
            return "-"
        return format_html("<pre>{}</pre>", json.dumps(obj.raw_data, indent=2))

    raw_data_formatted.short_description = "Raw Data"

    def response_actions_formatted(self, obj):
        """Format response actions as readable list."""
        if not obj.response_actions:
            return "-"
        return format_html("<pre>{}</pre>", json.dumps(obj.response_actions, indent=2))

    response_actions_formatted.short_description = "Response Actions"


@admin.register(ComplianceReport)
class ComplianceReportAdmin(admin.ModelAdmin):
    """Admin interface for compliance reports."""

    list_display = [
        "title",
        "report_type",
        "start_date",
        "end_date",
        "generated_by",
        "created_at",
        "file_hash",
    ]
    list_filter = [
        "report_type",
        "created_at",
        ("generated_by", admin.RelatedOnlyFieldListFilter),
    ]
    search_fields = ["title", "generated_by__email"]
    readonly_fields = [
        "created_at",
        "updated_at",
        "file_hash",
        "summary_formatted",
        "findings_formatted",
        "recommendations_formatted",
    ]
    date_hierarchy = "created_at"
    ordering = ["-created_at"]

    fieldsets = (
        (
            "Report Information",
            {"fields": ("title", "report_type", "generated_by", "created_at")},
        ),
        ("Date Range", {"fields": ("start_date", "end_date")}),
        (
            "Content",
            {
                "fields": (
                    "summary_formatted",
                    "findings_formatted",
                    "recommendations_formatted",
                )
            },
        ),
        ("File Information", {"fields": ("report_file_path", "file_hash")}),
    )

    def summary_formatted(self, obj):
        """Format summary as readable JSON."""
        if not obj.summary:
            return "-"
        return format_html("<pre>{}</pre>", json.dumps(obj.summary, indent=2))

    summary_formatted.short_description = "Summary"

    def findings_formatted(self, obj):
        """Format findings as readable JSON."""
        if not obj.findings:
            return "-"
        return format_html("<pre>{}</pre>", json.dumps(obj.findings, indent=2))

    findings_formatted.short_description = "Findings"

    def recommendations_formatted(self, obj):
        """Format recommendations as readable JSON."""
        if not obj.recommendations:
            return "-"
        return format_html("<pre>{}</pre>", json.dumps(obj.recommendations, indent=2))

    recommendations_formatted.short_description = "Recommendations"


# Custom admin site configuration for enhanced security
class SecureAuditAdminSite(admin.AdminSite):
    """Custom admin site with enhanced audit trail security."""

    site_header = "Savannah Audit & Compliance"
    site_title = "Audit Trail Administration"
    index_title = "Compliance Dashboard"

    def has_permission(self, request):
        """Enhanced permission checking for audit access."""
        # Only superusers and specific audit staff can access
        return (
            request.user.is_active
            and request.user.is_staff
            and (
                request.user.is_superuser
                or request.user.groups.filter(name="audit_staff").exists()
            )
        )


# Register a separate admin site for audit trails
audit_admin_site = SecureAuditAdminSite(name="audit_admin")
