from celery import shared_task
from django.db.models import Count
from django.core.cache import cache

from .models import Device


@shared_task
def refresh_device_stats() -> dict[str, int]:
    grouped = Device.objects.values('status').annotate(total=Count('id'))
    stats = {
        'total': Device.objects.count(),
        'online': 0,
        'offline': 0,
        'maintaining': 0,
    }
    for item in grouped:
        stats[item['status']] = item['total']
    cache.set('device_stats', stats, timeout=300)
    return stats
