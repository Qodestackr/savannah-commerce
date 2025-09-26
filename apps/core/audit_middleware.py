"""
Robust audit trail middleware and decorators.
Automatically tracks all model changes and API access for compliance.
"""

from django.utils.deprecation import MiddlewareMixin
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db import transaction
from .audit import AuditEvent, DataAccessLog
import uuid
import threading
import json

User = get_user_model()

# Thread-local storage for correlation IDs
_thread_locals = threading.local()


class AuditTrailMiddleware(MiddlewareMixin):
    """
    Middleware to automatically capture audit information for all requests.
    Creates correlation IDs and tracks API access patterns.
    """

    def process_request(self, request):
        """Initialize audit context for request."""
        # Generate correlation ID for this request
        correlation_id = uuid.uuid4()
        _thread_locals.correlation_id = correlation_id
        _thread_locals.user = getattr(request, "user", None)
        _thread_locals.ip_address = self.get_client_ip(request)
        _thread_locals.user_agent = request.META.get("HTTP_USER_AGENT", "")
        _thread_locals.request_method = request.method
        _thread_locals.request_path = request.path
        _thread_locals.session_key = (
            request.session.session_key if hasattr(request, "session") else ""
        )

        # Track API access
        if request.path.startswith("/api/"):
            self.log_api_access(request)

    def process_response(self, request, response):
        """Clean up thread-local data."""
        # Clear thread-local data
        for attr in [
            "correlation_id",
            "user",
            "ip_address",
            "user_agent",
            "request_method",
            "request_path",
            "session_key",
        ]:
            if hasattr(_thread_locals, attr):
                delattr(_thread_locals, attr)
        return response

    def get_client_ip(self, request):
        """Extract real client IP address."""
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            ip = x_forwarded_for.split(",")[0].strip()
        else:
            ip = request.META.get("REMOTE_ADDR")
        return ip

    def log_api_access(self, request):
        """Log API access for compliance monitoring."""
        if not hasattr(request, "user") or not request.user.is_authenticated:
            return

        # Determine access type based on method
        access_type_mapping = {
            "GET": "READ",
            "POST": "CREATE",
            "PUT": "UPDATE",
            "PATCH": "UPDATE",
            "DELETE": "DELETE",
        }

        access_type = access_type_mapping.get(request.method, "READ")
        if "search" in request.path.lower() or request.GET.get("search"):
            access_type = "SEARCH"

        # Extract query parameters for audit
        query_filters = {}
        for key, value in request.GET.items():
            if key not in ["page", "limit", "offset"]:  # Exclude pagination
                query_filters[key] = value

        try:
            DataAccessLog.objects.create(
                user=request.user,
                access_type=access_type,
                resource_type=self.extract_resource_type(request.path),
                resource_ids=[],  # Will be populated by view decorators
                ip_address=self.get_client_ip(request),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
                api_endpoint=request.path,
                query_filters=query_filters,
            )
        except Exception:
            # Don't break request if audit logging fails
            pass

    def extract_resource_type(self, path):
        """Extract resource type from API path."""
        path_parts = path.strip("/").split("/")
        if len(path_parts) >= 2 and path_parts[0] == "api":
            return path_parts[1]  # e.g., 'products', 'orders'
        return "unknown"


def get_audit_context():
    """Get current audit context from thread-local storage."""
    return {
        "correlation_id": getattr(_thread_locals, "correlation_id", None),
        "user": getattr(_thread_locals, "user", None),
        "ip_address": getattr(_thread_locals, "ip_address", None),
        "user_agent": getattr(_thread_locals, "user_agent", ""),
        "request_method": getattr(_thread_locals, "request_method", ""),
        "request_path": getattr(_thread_locals, "request_path", ""),
        "session_key": getattr(_thread_locals, "session_key", ""),
    }


def create_audit_event(action_type, description, **kwargs):
    """
    Create an audit event with current context.

    Args:
        action_type: Type of action (from AuditEvent.ACTION_TYPES)
        description: Human-readable description
        **kwargs: Additional audit data
    """
    context = get_audit_context()

    audit_data = {
        "action_type": action_type,
        "description": description,
        "correlation_id": context["correlation_id"],
        "user": context["user"]
        if context["user"] and context["user"].is_authenticated
        else None,
        "user_email": context["user"].email
        if context["user"] and context["user"].is_authenticated
        else "",
        "ip_address": context["ip_address"],
        "user_agent": context["user_agent"],
        "request_method": context["request_method"],
        "request_path": context["request_path"],
        "session_key": context["session_key"],
        **kwargs,
    }

    # Remove None values
    audit_data = {k: v for k, v in audit_data.items() if v is not None}

    try:
        return AuditEvent.objects.create(**audit_data)
    except Exception:
        # Don't break operations if audit fails
        return None


class AuditableMixin:
    """
    Mixin to add automatic audit trail to Django models.
    Override save() and delete() to track changes.
    """

    def save(self, *args, **kwargs):
        """Override save to create audit trail."""
        is_new = self.pk is None
        old_values = {}
        changed_fields = []

        if not is_new:
            # Get old values for comparison
            try:
                old_instance = self.__class__.objects.get(pk=self.pk)
                old_values = self._get_field_values(old_instance)
                new_values = self._get_field_values(self)

                # Find changed fields
                for field_name, new_value in new_values.items():
                    old_value = old_values.get(field_name)
                    if old_value != new_value:
                        changed_fields.append(field_name)
            except self.__class__.DoesNotExist:
                pass

        result = super().save(*args, **kwargs)

        # Create audit event
        action_type = "CREATE" if is_new else "UPDATE"
        description = f"{self.__class__.__name__} {action_type.lower()}d: {str(self)}"

        # Determine risk level based on model and changes
        risk_level = self._calculate_risk_level(action_type, changed_fields)

        create_audit_event(
            action_type=action_type,
            description=description,
            content_type=ContentType.objects.get_for_model(self),
            object_id=str(self.pk),
            object_repr=str(self),
            changed_fields=changed_fields,
            old_values=old_values,
            new_values=self._get_field_values(self) if changed_fields else {},
            risk_level=risk_level,
            regulation_tags=self._get_regulation_tags(),
            is_sensitive=self._is_sensitive_data(),
        )

        return result

    def delete(self, *args, **kwargs):
        """Override delete to create audit trail."""
        # Store values before deletion
        old_values = self._get_field_values(self)
        object_repr = str(self)
        content_type = ContentType.objects.get_for_model(self)
        object_id = str(self.pk)

        # Delete the model
        result = super().delete(*args, **kwargs)

        create_audit_event(
            action_type="DELETE",
            description=f"{self.__class__.__name__} deleted: {object_repr}",
            content_type=content_type,
            object_id=object_id,
            object_repr=object_repr,
            old_values=old_values,
            risk_level="HIGH",  # Deletions are always high risk
            regulation_tags=self._get_regulation_tags(),
            is_sensitive=self._is_sensitive_data(),
        )

        return result

    def _get_field_values(self, instance):
        """Extract field values for audit trail."""
        values = {}
        for field in instance._meta.fields:
            if field.name not in ["created_at", "updated_at"]:  # Skip timestamp fields
                try:
                    value = getattr(instance, field.name)
                    # Convert to JSON-serializable format
                    if hasattr(value, "isoformat"):  # datetime objects
                        value = value.isoformat()
                    elif hasattr(value, "__dict__"):  # Model instances
                        value = str(value)
                    values[field.name] = value
                except Exception:
                    values[field.name] = None
        return values

    def _calculate_risk_level(self, action_type, changed_fields):
        """Calculate risk level for the operation."""
        # High-risk actions
        if action_type == "DELETE":
            return "HIGH"

        high_risk_fields = [
            "email",
            "is_staff",
            "is_superuser",
            "price",
            "stock_quantity",
        ]
        if any(field in high_risk_fields for field in changed_fields):
            return "HIGH"

        # Medium-risk for creates and multiple field changes
        if action_type == "CREATE" or len(changed_fields) > 3:
            return "MEDIUM"

        return "LOW"

    def _get_regulation_tags(self):
        """Get applicable regulation tags for this model."""
        base_tags = ["SOX", "GDPR"]  # Basic compliance

        # if self.__class__.__name__ in ['User', 'Order', 'Product']:
        #     base_tags.extend(['FDA_21CFR11'])

        return base_tags

    def _is_sensitive_data(self):
        """Determine if this model contains sensitive data."""
        sensitive_models = ["User", "Order"]
        return self.__class__.__name__ in sensitive_models


def audit_view_access(resource_type=None, sensitive=False):
    """
    Decorator to audit data access in views.

    Usage:
        @audit_view_access(resource_type='products', sensitive=True)
        def product_list(request):
            ...
    """

    def decorator(view_func):
        def wrapped_view(request, *args, **kwargs):
            # Execute the view
            response = view_func(request, *args, **kwargs)

            # Create audit event for data access
            if request.user.is_authenticated:
                create_audit_event(
                    action_type="VIEW",
                    description=f"Accessed {resource_type or 'data'} via {request.path}",
                    risk_level="HIGH" if sensitive else "LOW",
                    is_sensitive=sensitive,
                    additional_data={
                        "view_name": view_func.__name__,
                        "status_code": getattr(response, "status_code", None),
                    },
                )

            return response

        return wrapped_view

    return decorator


def audit_bulk_operation(operation_type, resource_type):
    """
    Decorator for bulk operations that need special audit handling.

    Usage:
        @audit_bulk_operation('DELETE', 'products')
        def bulk_delete_products(request):
            ...
    """

    def decorator(view_func):
        def wrapped_view(request, *args, **kwargs):
            # Execute the view
            response = view_func(request, *args, **kwargs)

            # Create high-risk audit event for bulk operations
            create_audit_event(
                action_type="BULK_OPERATION",
                description=f"Bulk {operation_type} on {resource_type}",
                risk_level="CRITICAL",
                is_sensitive=True,
                regulation_tags=["HIPAA", "SOX", "GDPR"],
                additional_data={
                    "operation_type": operation_type,
                    "resource_type": resource_type,
                    "view_name": view_func.__name__,
                },
            )

            return response

        return wrapped_view

    return decorator
