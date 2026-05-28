from django.core.management.base import BaseCommand
from django_celery_beat.models import CrontabSchedule, PeriodicTask


class Command(BaseCommand):
    help = '初始化系统运维周期任务'

    def handle(self, *args, **options):
        schedule, _ = CrontabSchedule.objects.get_or_create(
            minute='0',
            hour='3',
            day_of_week='*',
            day_of_month='*',
            month_of_year='*',
            timezone='Asia/Shanghai',
        )
        PeriodicTask.objects.update_or_create(
            name='清理 7 天前 Celery 任务结果',
            defaults={
                'task': 'config.tasks.cleanup_old_celery_results',
                'crontab': schedule,
                'enabled': True,
            },
        )
        self.stdout.write(self.style.SUCCESS('系统运维周期任务已初始化。'))
