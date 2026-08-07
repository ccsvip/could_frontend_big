from django.core.management.base import BaseCommand, CommandError

from apps.ai_models.models import AgentApplication
from apps.ai_models.services.annotation_embeddings import reindex_annotation_embeddings
from apps.tenants.models import Tenant


class Command(BaseCommand):
    help = 'Rebuild agent annotation embeddings for the current tenant embedding model fingerprint'

    def add_arguments(self, parser):
        parser.add_argument('--tenant', type=int, dest='tenant_id', help='Tenant id to reindex')
        parser.add_argument('--application', type=int, dest='application_id', help='Agent application id to reindex')
        parser.add_argument('--force', action='store_true', help='Force rebuild even when ready vectors exist')

    def handle(self, *args, **options):
        tenant = None
        application = None
        tenant_id = options.get('tenant_id')
        application_id = options.get('application_id')
        force = bool(options.get('force'))

        if application_id is not None:
            application = AgentApplication.objects.filter(id=application_id).first()
            if application is None:
                raise CommandError(f'application not found: {application_id}')
            tenant = application.tenant

        if tenant_id is not None:
            tenant = Tenant.objects.filter(id=tenant_id).first()
            if tenant is None:
                raise CommandError(f'tenant not found: {tenant_id}')
            if application is not None and application.tenant_id != tenant.id:
                raise CommandError('application does not belong to the given tenant')

        stats = reindex_annotation_embeddings(tenant=tenant, application=application, force=force)
        self.stdout.write(
            self.style.SUCCESS(
                'reindex_annotation_embeddings '
                f"total={stats['total']} ready={stats['ready']} failed={stats['failed']} skipped={stats['skipped']}"
            )
        )
