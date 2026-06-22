from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.devices.models import Device, DeviceApplication, DeviceGroup
from apps.tenants.models import Tenant


class Command(BaseCommand):
    help = 'Seed initial device authorization data'

    def handle(self, *args, **options):
        tenant = Tenant.objects.filter(is_legacy=True).first() or Tenant.objects.first()
        if tenant is None:
            self.stdout.write(self.style.WARNING('No tenant found, skipped device seeds.'))
            return

        application, _ = DeviceApplication.objects.update_or_create(
            tenant=tenant,
            code='demo-android-app',
            defaults={
                'name': '演示安卓数字人应用',
                'description': '开发环境默认设备应用',
                'is_active': True,
            },
        )
        group, _ = DeviceGroup.objects.update_or_create(
            tenant=tenant,
            name='演示设备',
            defaults={'remark': '开发环境默认设备分组'},
        )

        seed_data = [
            {
                'code': 'ANDROID-DEMO-10001',
                'name': '大厅安卓设备 A1',
                'status': Device.STATUS_ONLINE,
                'software_version': '1.0.0',
                'system_version': 'Android 14',
                'mainboard_info': 'demo-board-a1',
            },
            {
                'code': 'ANDROID-DEMO-10002',
                'name': '展厅安卓设备 B2',
                'status': Device.STATUS_OFFLINE,
                'software_version': '1.0.0',
                'system_version': 'Android 13',
                'mainboard_info': 'demo-board-b2',
            },
        ]
        now = timezone.now()
        for item in seed_data:
            Device.objects.update_or_create(
                code=item['code'],
                defaults={
                    'tenant': tenant,
                    'application': application,
                    'group': group,
                    'name': item['name'],
                    'status': item['status'],
                    'authorization_type': Device.AUTHORIZATION_PERMANENT,
                    'software_version': item['software_version'],
                    'system_version': item['system_version'],
                    'mainboard_info': item['mainboard_info'],
                    'registered_at': now,
                    'last_auth_at': now,
                    'last_heartbeat': now if item['status'] == Device.STATUS_ONLINE else None,
                },
            )
        self.stdout.write(self.style.SUCCESS('Seeded device authorization data successfully.'))
