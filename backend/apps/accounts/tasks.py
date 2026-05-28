from celery import shared_task

from .models import AccountApplication
from .services.notifications import notify_account_application_created


@shared_task
def notify_account_application(application_id: int) -> str:
    application = AccountApplication.objects.get(pk=application_id)
    notified = notify_account_application_created(application)
    return f'account_application_notified:{application_id}:{notified}'
