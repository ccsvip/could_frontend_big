from django.test import SimpleTestCase

from config.sentry import before_send


class SentryFilterTests(SimpleTestCase):
    def test_drops_celery_worker_redis_reconnect_during_restart(self):
        event = {
            'logger': 'celery.worker.consumer.consumer',
            'message': (
                'consumer: Cannot connect to redis://redis:6379/1: '
                'Error 111 connecting to redis:6379. Connection refused..\n'
                'Trying again in 2.00 seconds... (1/100)'
            ),
            'extra': {
                'sys.argv': ['/usr/local/bin/celery', '-A', 'config', 'worker', '-l', 'info'],
            },
        }

        self.assertIsNone(before_send(event, {}))

    def test_drops_celery_beat_database_shutdown_during_restart(self):
        event = {
            'exception': {
                'values': [
                    {
                        'type': 'OperationalError',
                        'value': 'terminating connection due to administrator command',
                    },
                ],
            },
            'extra': {
                'sys.argv': [
                    '/usr/local/bin/celery',
                    '-A',
                    'config',
                    'beat',
                    '-l',
                    'info',
                    '--scheduler',
                    'django_celery_beat.schedulers:DatabaseScheduler',
                ],
            },
        }

        self.assertIsNone(before_send(event, {}))

    def test_keeps_same_messages_outside_celery_processes(self):
        event = {
            'logger': 'django.request',
            'message': 'Cannot connect to redis://redis:6379/1: Connection refused.',
            'extra': {
                'sys.argv': ['/usr/local/bin/uvicorn', 'config.asgi:application'],
            },
        }

        self.assertIs(before_send(event, {}), event)

    def test_keeps_unrelated_celery_errors(self):
        event = {
            'logger': 'celery.worker.strategy',
            'message': 'Task apps.resources.tasks.notify_command_event_task raised unexpected RuntimeError',
            'extra': {
                'sys.argv': ['/usr/local/bin/celery', '-A', 'config', 'worker', '-l', 'info'],
            },
        }

        self.assertIs(before_send(event, {}), event)
