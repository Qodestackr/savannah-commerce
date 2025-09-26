import time

from django.contrib.auth import get_user_model
from django.core.cache import cache

from rest_framework.throttling import (
    AnonRateThrottle,
    SimpleRateThrottle,
    UserRateThrottle,
)

User = get_user_model()


class BurstRateThrottle(UserRateThrottle):
    """
    Throttle for handling burst requests - allows higher frequency for short periods.
    """

    scope = "burst"

    def get_cache_key(self, request, view):
        if request.user.is_authenticated:
            ident = request.user.pk
        else:
            ident = self.get_ident(request)

        return self.cache_format % {"scope": self.scope, "ident": ident}


class SustainedRateThrottle(UserRateThrottle):
    """
    Throttle for sustained usage - lower rate over longer periods.
    """

    scope = "sustained"


class PremiumUserThrottle(UserRateThrottle):
    """
    Higher rate limits for premium/admin users.
    """

    scope = "premium"

    def allow_request(self, request, view):
        # Admin users get higher limits
        if request.user.is_staff:
            return True

        return super().allow_request(request, view)


class AnonymousThrottle(AnonRateThrottle):
    """
    Throttle for anonymous users with stricter limits.
    """

    scope = "anon"


class LoginRateThrottle(SimpleRateThrottle):
    """
    Special throttle for login attempts to prevent brute force.
    """

    scope = "login"

    def get_cache_key(self, request, view):
        # Use IP address for login throttling
        ident = self.get_ident(request)
        return self.cache_format % {"scope": self.scope, "ident": ident}


class OrderCreationThrottle(UserRateThrottle):
    """
    Special throttle for order creation to prevent spam orders.
    """

    scope = "order_create"

    def allow_request(self, request, view):
        # Only throttle POST requests (order creation)
        if request.method != "POST":
            return True

        return super().allow_request(request, view)


class SMSThrottle(SimpleRateThrottle):
    """
    Throttle for SMS sending to prevent abuse.
    """

    scope = "sms"

    def get_cache_key(self, request, view):
        if request.user.is_authenticated:
            ident = request.user.pk
        else:
            ident = self.get_ident(request)

        return self.cache_format % {"scope": self.scope, "ident": ident}


class PerEndpointThrottle(SimpleRateThrottle):
    """
    Throttle per endpoint for granular control.
    """

    def __init__(self):
        super().__init__()
        self.scope = getattr(self, "scope", "endpoint")

    def get_cache_key(self, request, view):
        if request.user.is_authenticated:
            ident = request.user.pk
        else:
            ident = self.get_ident(request)

        # Include view name in cache key for per-endpoint throttling
        endpoint = f"{view.__class__.__name__}_{request.method.lower()}"

        return f"throttle_{self.scope}_{endpoint}_{ident}"


class DynamicRateThrottle(UserRateThrottle):
    """
    Dynamic throttle that adjusts based on user behavior.
    """

    def __init__(self):
        super().__init__()
        self.scope = "dynamic"

    def get_rate(self):
        """
        Override to provide dynamic rates based on user type.
        """
        if not hasattr(self, "request"):
            return super().get_rate()

        user = getattr(self.request, "user", None)
        if user and user.is_authenticated:
            if user.is_staff:
                return "1000/hour"  # Higher rate for staff
            elif hasattr(user, "customer_profile"):
                return "100/hour"  # Standard rate for customers
            else:
                return "50/hour"  # Lower rate for basic users

        return "20/hour"  # Very low rate for anonymous users

    def allow_request(self, request, view):
        self.request = request
        return super().allow_request(request, view)


class ConditionalThrottle(SimpleRateThrottle):
    """
    Throttle that can be conditionally applied based on request content.
    """

    scope = "conditional"

    def allow_request(self, request, view):
        # Example: Only throttle expensive operations
        if hasattr(view, "action") and view.action in ["list", "create"]:
            return super().allow_request(request, view)

        # Don't throttle other actions
        return True

    def get_cache_key(self, request, view):
        if request.user.is_authenticated:
            ident = request.user.pk
        else:
            ident = self.get_ident(request)

        action = getattr(view, "action", "unknown")
        return f"throttle_{self.scope}_{action}_{ident}"


# Throttle configuration mapping
THROTTLE_CLASSES = {
    "burst": BurstRateThrottle,
    "sustained": SustainedRateThrottle,
    "premium": PremiumUserThrottle,
    "anon": AnonymousThrottle,
    "login": LoginRateThrottle,
    "order_create": OrderCreationThrottle,
    "sms": SMSThrottle,
    "endpoint": PerEndpointThrottle,
    "dynamic": DynamicRateThrottle,
    "conditional": ConditionalThrottle,
}
