from django.db import migrations, models


def migrate_existing_reply_text(apps, schema_editor):
    AgentAnnotation = apps.get_model('ai_models', 'AgentAnnotation')
    AgentApplication = apps.get_model('ai_models', 'AgentApplication')
    ChatMessage = apps.get_model('ai_models', 'ChatMessage')
    for annotation in AgentAnnotation.objects.all().iterator():
        answer = (annotation.answer or '').strip()
        annotation.answer_blocks = [{'type': 'text', 'text': answer}] if answer else []
        annotation.save(update_fields=['answer_blocks'])
    for message in ChatMessage.objects.all().iterator():
        content = (message.content or '').strip()
        message.content_blocks = [{'type': 'text', 'text': content}] if content else []
        message.save(update_fields=['content_blocks'])
    for application in AgentApplication.objects.exclude(published_at__isnull=True).iterator():
        snapshots = []
        for annotation in AgentAnnotation.objects.filter(application=application, is_active=True).order_by('id'):
            snapshots.append({
                'id': annotation.id,
                'question': annotation.question,
                'answer': annotation.answer,
                'answerBlocks': annotation.answer_blocks,
                'isActive': annotation.is_active,
            })
        application.published_annotations = snapshots
        application.save(update_fields=['published_annotations'])


class Migration(migrations.Migration):

    dependencies = [
        ('ai_models', '0030_move_tts_session_config_to_provider'),
    ]

    operations = [
        migrations.AddField(
            model_name='agentapplication',
            name='published_annotations',
            field=models.JSONField(blank=True, default=list, verbose_name='已发布标注'),
        ),
        migrations.AddField(
            model_name='agentannotation',
            name='answer_blocks',
            field=models.JSONField(blank=True, default=list, verbose_name='标准回复内容块'),
        ),
        migrations.AddField(
            model_name='chatmessage',
            name='content_blocks',
            field=models.JSONField(blank=True, default=list, verbose_name='消息内容块'),
        ),
        migrations.RunPython(migrate_existing_reply_text, migrations.RunPython.noop),
    ]
