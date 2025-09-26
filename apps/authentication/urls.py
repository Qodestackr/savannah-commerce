from django.urls import include, path

from rest_framework.routers import DefaultRouter

from . import views

app_name = "authentication"

urlpatterns = [
    path("auth/register/", views.register_user, name="register"),
    path("auth/profile/", views.UserProfileView.as_view(), name="user-profile"),
    path(
        "auth/customer/", views.CustomerProfileView.as_view(), name="customer-profile"
    ),
]
