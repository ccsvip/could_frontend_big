from django.contrib import admin

from .models import Device


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'location', 'status', 'last_heartbeat')
    list_filter = ('status', 'last_heartbeat')
    search_fields = ('code', 'name', 'location')
