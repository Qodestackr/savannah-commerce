from django.contrib import admin
from .models import NotificationTemplate, NotificationLog


@admin.register(NotificationTemplate)
class NotificationTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'template_type', 'is_active', 'created_at')
    list_filter = ('template_type', 'is_active', 'created_at')
    search_fields = ('name', 'subject', 'content')
    ordering = ('-created_at',)


@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    list_display = ('recipient', 'template', 'status', 'sent_at', 'created_at')
    list_filter = ('status', 'template__template_type', 'created_at')
    search_fields = ('recipient__email', 'recipient_email', 'recipient_phone')
    ordering = ('-created_at',)
    readonly_fields = ('sent_at', 'created_at', 'updated_at')