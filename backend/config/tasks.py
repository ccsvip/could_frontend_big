from datetime import timedelta

from celery import shared_task
from django.utils import timezone
from django_celery_results.models import TaskResult


@shared_task
def cleanup_old_celery_results(days: int = 7) -> int:
    """清理旧 Celery 结果，只保留近期排障价值，避免结果表无限增长。"""
    cutoff = timezone.now() - timedelta(days=days)
    deleted_count, _ = TaskResult.objects.filter(date_done__lt=cutoff).delete()
    return deleted_count
