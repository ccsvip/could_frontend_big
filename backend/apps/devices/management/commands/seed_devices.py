from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.devices.models import Device


class Command(BaseCommand):
    help = 'Seed initial device data'

    def handle(self, *args, **options):
        seed_data = [
            {
                'code': 'DV-10001',
                'name': '数字人交互终端-上海A1',
                'location': '上海 · 展厅 A 区',
                'status': Device.STATUS_ONLINE,
            },
            {
                'code': 'DV-10002',
                'name': '数字人交互终端-北京B2',
                'location': '北京 · 会议中心 B2',
                'status': Device.STATUS_MAINTAINING,
            },
            {
                'code': 'DV-10003',
                'name': '数字人交互终端-深圳C3',
                'location': '深圳 · 体验店 C3',
                'status': Device.STATUS_OFFLINE,
            },
        ]
        for item in seed_data:
            Device.objects.update_or_create(
                code=item['code'],
                defaults={
                    'name': item['name'],
                    'location': item['location'],
                    'status': item['status'],
                    'last_heartbeat': timezone.now(),
                },
            )
        self.stdout.write(self.style.SUCCESS('Seeded devices successfully.'))
