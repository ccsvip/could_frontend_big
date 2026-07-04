from django.test import SimpleTestCase

from config.sentry import before_send


class BeforeSendFilterTests(SimpleTestCase):
    """验证 before_send 过滤掉不应上报到 production Sentry 的噪音 event。"""

    def test_manage_py_test_argv_is_dropped(self):
        """`manage.py test` 产生的 event（如测试故意触发的 embedding 失败）不应上报。"""
        event = {
            'extra': {
                'sys.argv': [
                    'manage.py',
                    'test',
                    'apps.ai_models.tests.test_agent_knowledge_service',
                    '--keepdb',
                ]
            }
        }
        self.assertIsNone(before_send(event, {}))

    def test_manage_py_test_with_full_path_is_dropped(self):
        event = {
            'extra': {
                'sys.argv': [
                    '/app/manage.py',
                    'test',
                    'apps.resources',
                ]
            }
        }
        self.assertIsNone(before_send(event, {}))

    def test_uvicorn_argv_is_kept(self):
        """生产 uvicorn 进程的 event 应正常上报。"""
        event = {
            'extra': {
                'sys.argv': [
                    '/usr/local/bin/uvicorn',
                    'config.asgi:application',
                    '--host',
                    '0.0.0.0',
                ]
            }
        }
        self.assertIsNotNone(before_send(event, {}))

    def test_celery_argv_is_kept(self):
        event = {
            'extra': {
                'sys.argv': ['/usr/local/bin/celery', '-A', 'config', 'worker', '-l', 'info']
            }
        }
        self.assertIsNotNone(before_send(event, {}))

    def test_missing_argv_is_kept(self):
        """没有 sys.argv 信息的 event（非 Python 运行时或旧 SDK）应保留。"""
        self.assertIsNotNone(before_send({}, {}))
        self.assertIsNotNone(before_send({'extra': {}}, {}))
