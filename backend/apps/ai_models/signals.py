from __future__ import annotations

import logging

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(pre_save, sender='ai_models.EmbeddingModel')
def cache_embedding_model_fingerprint_fields(sender, instance, **kwargs):
    if not instance.pk:
        instance._annotation_prev_fingerprint_fields = None
        return
    previous = (
        sender.objects.filter(pk=instance.pk)
        .values('code', 'model', 'dimensions')
        .first()
    )
    instance._annotation_prev_fingerprint_fields = previous


@receiver(post_save, sender='ai_models.EmbeddingModel')
def reindex_annotations_on_embedding_model_change(sender, instance, created, **kwargs):
    if created:
        return
    previous = getattr(instance, '_annotation_prev_fingerprint_fields', None)
    if not previous:
        return
    if (
        previous.get('code') == instance.code
        and previous.get('model') == instance.model
        and previous.get('dimensions') == instance.dimensions
    ):
        return

    try:
        from apps.ai_models.models import TenantKnowledgeModelSettings
        from apps.ai_models.services.annotation_embeddings import reindex_annotation_embeddings
        from apps.tenants.models import Tenant

        tenant_ids = list(
            TenantKnowledgeModelSettings.objects.filter(
                embedding_model_id=instance.pk,
                is_active=True,
            ).values_list('tenant_id', flat=True)
        )
        for tenant_id in tenant_ids:
            tenant = Tenant.objects.filter(id=tenant_id).first()
            if tenant is not None:
                reindex_annotation_embeddings(tenant=tenant)
    except Exception:
        logger.exception(
            'annotation.reindex.after_embedding_model_field_change failed embedding_model_id=%s',
            instance.pk,
        )
