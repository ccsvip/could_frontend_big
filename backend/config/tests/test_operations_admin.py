from datetime import timedelta
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import management
from django.test import TestCase, override_settings
from django.utils import timezone

from django_celery_beat.models import CrontabSchedule, PeriodicTask
from django_celery_results.models import TaskResult

User = get_user_model()


@override_settings(
    CACHES={
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'operations-admin-tests',
        }
    }
)
class OperationsAdminTests(TestCase):
    def setUp(self):
        self.superuser = User.objects.create_superuser(username='ops-admin', password='test123456')
        self.staff_user = User.objects.create_user(
            username='ops-staff',
            password='test123456',
            is_staff=True,
        )

    def test_superuser_can_open_operations_dashboard(self):
        self.client.force_login(self.superuser)

        with patch('config.operations_admin.get_operations_context', return_value=self.make_context()):
            response = self.client.get('/admin/operations/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '系统运维')
        self.assertContains(response, 'apps.resources.tasks.notify_command_event_task')

    def test_staff_user_without_superuser_permission_gets_403(self):
        self.client.force_login(self.staff_user)

        response = self.client.get('/admin/operations/')

        self.assertEqual(response.status_code, 403)

    def test_operations_dashboard_is_visible_in_simpleui_menu(self):
        system_tools_menu = next(
            menu for menu in settings.SIMPLEUI_CONFIG['menus'] if menu['name'] == '系统工具'
        )

        self.assertIn(
            {'name': '系统运维', 'icon': 'fas fa-heartbeat', 'url': '/admin/operations/'},
            system_tools_menu['models'],
        )

    def test_dashboard_degrades_when_celery_inspect_fails(self):
        self.client.force_login(self.superuser)

        with patch('config.operations_admin.get_celery_worker_status') as worker_status:
            worker_status.return_value = {
                'ok': False,
                'label': '异常',
                'message': 'worker inspect failed',
                'registered_tasks': [],
                'nodes': [],
            }
            response = self.client.get('/admin/operations/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'worker inspect failed')

    def test_manual_refresh_device_stats_uses_whitelisted_task(self):
        self.client.force_login(self.superuser)

        with patch('config.operations_admin.refresh_device_stats.delay') as delay_task:
            response = self.client.post(
                '/admin/operations/',
                {'action': 'refresh_device_stats'},
                follow=True,
            )

        self.assertEqual(response.status_code, 200)
        delay_task.assert_called_once_with()
        self.assertContains(response, '已投递设备统计刷新任务')

    def test_unknown_manual_action_is_rejected(self):
        self.client.force_login(self.superuser)

        response = self.client.post(
            '/admin/operations/',
            {'action': 'restart_docker'},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '未知运维操作，未执行')

    def test_recent_task_results_are_limited_and_use_task_name_fallback(self):
        self.client.force_login(self.superuser)
        now = timezone.now()
        for index in range(55):
            result = TaskResult.objects.create(
                task_id=f'task-{index:02d}',
                task_name='' if index == 0 else f'apps.demo.task_{index:02d}',
                status='SUCCESS',
                result='{}',
            )
            # django-celery-results 会自动写入时间字段，测试中用 update 固定排序边界。
            TaskResult.objects.filter(pk=result.pk).update(
                date_created=now - timedelta(minutes=index),
                date_done=now - timedelta(minutes=index),
            )

        response = self.client.get('/admin/operations/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'task-00')
        self.assertNotContains(response, 'apps.demo.task_54')

    def test_cleanup_old_celery_results_removes_only_expired_results(self):
        from config.tasks import cleanup_old_celery_results

        old_result = TaskResult.objects.create(
            task_id='old-task',
            status='SUCCESS',
        )
        fresh_result = TaskResult.objects.create(
            task_id='fresh-task',
            status='SUCCESS',
        )
        # django-celery-results 自动维护完成时间，这里显式回写旧数据用于验证清理边界。
        TaskResult.objects.filter(pk=old_result.pk).update(
            date_created=timezone.now() - timedelta(days=8),
            date_done=timezone.now() - timedelta(days=8),
        )

        deleted_count = cleanup_old_celery_results.run()

        self.assertEqual(deleted_count, 1)
        self.assertFalse(TaskResult.objects.filter(pk=old_result.pk).exists())
        self.assertTrue(TaskResult.objects.filter(pk=fresh_result.pk).exists())

    def test_seed_operations_periodic_tasks_command_is_discoverable_and_idempotent(self):
        management.call_command('seed_operations_periodic_tasks', verbosity=0)
        management.call_command('seed_operations_periodic_tasks', verbosity=0)

        self.assertEqual(PeriodicTask.objects.filter(name='清理 7 天前 Celery 任务结果').count(), 1)
        task = PeriodicTask.objects.get(name='清理 7 天前 Celery 任务结果')
        self.assertEqual(task.task, 'config.tasks.cleanup_old_celery_results')
        self.assertIsInstance(task.crontab, CrontabSchedule)

    def test_celery_result_backend_uses_django_database(self):
        self.assertEqual(settings.CELERY_RESULT_BACKEND, 'django-db')
        self.assertTrue(settings.CELERY_RESULT_EXTENDED)

    def test_operations_cleanup_task_is_registered_by_celery_imports(self):
        from config.celery import app

        app.loader.import_default_modules()

        self.assertIn('config.tasks.cleanup_old_celery_results', app.tasks)

    @staticmethod
    def make_context():
        return {
            'title': '系统运维',
            'summary': {'ok': True, 'label': '正常', 'message': '运维状态正常'},
            'statuses': [
                {'name': '数据库', 'ok': True, 'label': '正常', 'message': '连接正常'},
            ],
            'worker_status': {
                'ok': True,
                'label': '正常',
                'message': 'worker 在线',
                'registered_tasks': ['apps.resources.tasks.notify_command_event_task'],
                'nodes': ['celery@test'],
            },
            'beat_status': {
                'ok': True,
                'label': '已配置',
                'message': '调度器配置正常',
            },
            'recent_results': [],
            'flower_url': '',
        }
