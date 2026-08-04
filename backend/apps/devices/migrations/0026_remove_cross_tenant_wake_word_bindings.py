from django.db import migrations


def remove_cross_tenant_wake_word_device_bindings(apps, schema_editor) -> None:
    connection = schema_editor.connection
    if connection.vendor != 'postgresql':
        return

    WakeWord = apps.get_model('devices', 'WakeWord')
    Device = apps.get_model('devices', 'Device')
    WakeWordDevice = WakeWord.devices.through
    quote_name = connection.ops.quote_name
    bindings_table = quote_name(WakeWordDevice._meta.db_table)
    wake_words_table = quote_name(WakeWord._meta.db_table)
    devices_table = quote_name(Device._meta.db_table)
    wake_word_column = quote_name(WakeWordDevice._meta.get_field('wakeword').column)
    device_column = quote_name(WakeWordDevice._meta.get_field('device').column)
    wake_word_tenant_column = quote_name(WakeWord._meta.get_field('tenant').column)
    device_tenant_column = quote_name(Device._meta.get_field('tenant').column)

    with connection.cursor() as cursor:
        cursor.execute(
            f'''
            DELETE FROM {bindings_table} AS binding
            USING {wake_words_table} AS wake_word, {devices_table} AS device
            WHERE binding.{wake_word_column} = wake_word.id
              AND binding.{device_column} = device.id
              AND (
                  wake_word.{wake_word_tenant_column} IS NULL
                  OR device.{device_tenant_column} IS NULL
                  OR wake_word.{wake_word_tenant_column} != device.{device_tenant_column}
              )
            '''
        )


class Migration(migrations.Migration):
    dependencies = [
        ('devices', '0025_repair_wakeword_primary_key'),
    ]

    operations = [
        migrations.RunPython(
            remove_cross_tenant_wake_word_device_bindings,
            migrations.RunPython.noop,
        ),
    ]
