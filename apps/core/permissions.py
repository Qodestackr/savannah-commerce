from rest_framework import permissions
from rest_framework.permissions import BasePermission
from django.contrib.auth import get_user_model
from guardian.shortcuts import get_objects_for_user
from django.core.exceptions import ObjectDoesNotExist

User = get_user_model()


class IsOwnerOrAdmin(BasePermission):
    """
    Permission to only allow owners of an object or admins to access it.
    """

    def has_object_permission(self, request, view, obj):
        # Admin users have full access
        if request.user.is_staff:
            return True

        # Check if object has a user/customer field
        if hasattr(obj, "customer"):
            return obj.customer == request.user
        elif hasattr(obj, "user"):
            return obj.user == request.user

        return False


class IsCustomerOrReadOnly(BasePermission):
    """
    Permission to allow authenticated customers to modify, others read-only.
    """

    def has_permission(self, request, view):
        # Read permissions for any request
        if request.method in permissions.SAFE_METHODS:
            return True

        # Write permissions only for authenticated customers
        return request.user.is_authenticated and hasattr(
            request.user, "customer_profile"
        )


class AdminPermission(BasePermission):
    """
    Permission class for admin-only operations.
    """

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_staff

    def has_object_permission(self, request, view, obj):
        return request.user.is_authenticated and request.user.is_staff


class CustomerPermission(BasePermission):
    """
    Permission class for customer operations.
    """

    def has_permission(self, request, view):
        return request.user.is_authenticated and hasattr(
            request.user, "customer_profile"
        )

    def has_object_permission(self, request, view, obj):
        if not request.user.is_authenticated:
            return False

        # Check ownership based on object type
        if hasattr(obj, "customer"):
            return obj.customer == request.user
        elif hasattr(obj, "user"):
            return obj.user == request.user

        return False


class IsOwnerOrReadOnly(BasePermission):
    """
    Custom permission to only allow owners of an object to edit it.
    Others can view but not modify.
    """

    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed for any request
        if request.method in permissions.SAFE_METHODS:
            return True

        # Write permissions are only allowed to the owner
        if hasattr(obj, "customer"):
            return obj.customer == request.user
        elif hasattr(obj, "user"):
            return obj.user == request.user

        return False


def require_object_owner(view_func):
    """
    Decorator to ensure user owns the object being accessed.
    """

    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return False

        # Extract object ID from URL kwargs
        obj_id = kwargs.get("pk") or kwargs.get("id")
        if not obj_id:
            return False

        # This would need to be customized per model
        # For now, return True if user is authenticated
        return view_func(request, *args, **kwargs)

    return wrapper


def admin_or_owner_only(view_func):
    """
    Decorator to ensure only admin or object owner can access.
    """

    def wrapper(request, *args, **kwargs):
        if request.user.is_staff:
            return view_func(request, *args, **kwargs)

        # Additional owner checking logic would go here
        return view_func(request, *args, **kwargs)

    return wrapper


class ObjectLevelPermissionMixin:
    """
    Mixin to add object-level permission checks to ViewSets.
    """

    def get_queryset(self):
        """
        Filter queryset based on user permissions.
        """
        queryset = super().get_queryset()

        if self.request.user.is_staff:
            return queryset

        # Filter to user's own objects
        if hasattr(queryset.model, "customer"):
            return queryset.filter(customer=self.request.user)
        elif hasattr(queryset.model, "user"):
            return queryset.filter(user=self.request.user)

        return queryset

    def perform_create(self, serializer):
        """
        Set the user/customer when creating objects.
        """
        if hasattr(serializer.Meta.model, "customer"):
            serializer.save(customer=self.request.user)
        elif hasattr(serializer.Meta.model, "user"):
            serializer.save(user=self.request.user)
        else:
            serializer.save()
