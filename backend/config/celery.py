import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')

app = Celery('config')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
# config 不是 INSTALLED_APPS，运维任务通过 Celery imports 在 worker 初始化后加载，避免 Django app registry 过早导入 ORM 模型。
app.conf.imports = tuple(app.conf.imports or ()) + ('config.tasks',)


@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
