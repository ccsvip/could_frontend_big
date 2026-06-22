from django.db import migrations, models


def consolidate_duplicate_device_codes(apps, schema_editor):
    Device = apps.get_model('devices', 'Device')
    DeviceAuthLog = apps.get_model('devices', 'DeviceAuthLog')
    DeviceAuthorizationCode = apps.get_model('devices', 'DeviceAuthorizationCode')
    duplicates = (
        Device.objects.values('code')
        .annotate(total=models.Count('id'))
        .filter(total__gt=1)
        .order_by('code')
    )
    for duplicate in duplicates:
        devices = list(
            Device.objects.filter(code=duplicate['code']).order_by(
                '-tenant_id',
                '-is_enabled',
                '-last_auth_at',
                '-last_heartbeat',
                '-updated_at',
                '-id',
            )
        )
        canonical = devices[0]
        duplicate_ids = [device.id for device in devices[1:]]

        for candidate in devices[1:]:
            update_fields = []
            for field in ('tenant_id', 'application_id', 'agent_application_id', 'group_id'):
                if getattr(canonical, field) is None and getattr(candidate, field) is not None:
                    setattr(canonical, field, getattr(candidate, field))
                    update_fields.append(field.replace('_id', ''))
            for field in ('name', 'location', 'software_version', 'system_version', 'mainboard_info'):
                if not getattr(canonical, field) and getattr(candidate, field):
                    setattr(canonical, field, getattr(candidate, field))
                    update_fields.append(field)
            for field in ('registered_at', 'last_auth_at', 'last_heartbeat'):
                canonical_value = getattr(canonical, field)
                candidate_value = getattr(candidate, field)
                if candidate_value is not None and (canonical_value is None or candidate_value > canonical_value):
                    setattr(canonical, field, candidate_value)
                    update_fields.append(field)
            if candidate.expires_at is not None and (
                canonical.expires_at is None or candidate.expires_at > canonical.expires_at
            ):
                canonical.expires_at = candidate.expires_at
                update_fields.append('expires_at')
            if candidate.status == 'online' and canonical.status != 'online':
                canonical.status = candidate.status
                update_fields.append('status')
            if candidate.is_enabled and not canonical.is_enabled:
                canonical.is_enabled = candidate.is_enabled
                update_fields.append('is_enabled')
            if update_fields:
                canonical.save(update_fields=sorted(set([*update_fields, 'updated_at'])))

        DeviceAuthLog.objects.filter(device_id__in=duplicate_ids).update(device_id=canonical.id)
        DeviceAuthorizationCode.objects.filter(used_by_device_id__in=duplicate_ids).update(
            used_by_device_id=canonical.id
        )
        Device.objects.filter(id__in=duplicate_ids).delete()


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ('devices', '0008_deviceauthlog_agent_application'),
    ]

    operations = [
        migrations.RunPython(consolidate_duplicate_device_codes, migrations.RunPython.noop),
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    'ALTER TABLE devices_device DROP CONSTRAINT IF EXISTS unique_device_code_per_tenant',
                    reverse_sql=migrations.RunSQL.noop,
                ),
            ],
            state_operations=[
                migrations.RemoveConstraint(
                    model_name='device',
                    name='unique_device_code_per_tenant',
                ),
            ],
        ),
        migrations.AlterField(
            model_name='device',
            name='code',
            field=models.CharField(max_length=128, unique=True, verbose_name='设备码'),
        ),
    ]
