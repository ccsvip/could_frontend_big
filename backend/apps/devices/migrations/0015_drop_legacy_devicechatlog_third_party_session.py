from django.db import migrations


def drop_legacy_third_party_session_id(apps, schema_editor):
    table_name = 'devices_devicechatlog'
    column_name = 'third_party_session_id'
    with schema_editor.connection.cursor() as cursor:
        columns = {
            column.name
            for column in schema_editor.connection.introspection.get_table_description(cursor, table_name)
        }
    if column_name not in columns:
        return
    quote_name = schema_editor.quote_name
    schema_editor.execute(
        f'ALTER TABLE {quote_name(table_name)} DROP COLUMN {quote_name(column_name)}'
    )


class Migration(migrations.Migration):

    dependencies = [
        ('devices', '0014_devicechatlog_answer_blocks'),
    ]

    operations = [
        migrations.RunPython(drop_legacy_third_party_session_id, migrations.RunPython.noop),
    ]
