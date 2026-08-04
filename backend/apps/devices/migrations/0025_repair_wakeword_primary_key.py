from django.db import migrations, transaction


def repair_wake_word_primary_key(connection, table_name: str) -> None:
    if connection.vendor != 'postgresql':
        return

    with transaction.atomic(using=connection.alias):
        _repair_wake_word_primary_key(connection, table_name)


def _repair_wake_word_primary_key(connection, table_name: str) -> None:
    quoted_table = connection.ops.quote_name(table_name)
    with connection.cursor() as cursor:
        cursor.execute(f'LOCK TABLE {quoted_table} IN ACCESS EXCLUSIVE MODE')
        cursor.execute(
            '''
            SELECT EXISTS(
                SELECT 1
                FROM pg_constraint
                WHERE conrelid = %s::regclass AND contype = 'p'
            )
            ''',
            [table_name],
        )
        if cursor.fetchone()[0]:
            return

        cursor.execute(
            f'''
            WITH ranked AS (
                SELECT
                    ctid,
                    id,
                    ROW_NUMBER() OVER (
                        PARTITION BY id
                        ORDER BY created_at ASC NULLS LAST, ctid
                    ) AS occurrence
                FROM {quoted_table}
            ),
            rows_to_reassign AS (
                SELECT
                    ctid,
                    ROW_NUMBER() OVER (ORDER BY id NULLS LAST, ctid) AS replacement_offset
                FROM ranked
                WHERE id IS NULL OR occurrence > 1
            ),
            maximum AS (
                SELECT COALESCE(MAX(id), 0) AS id FROM {quoted_table}
            )
            UPDATE {quoted_table} AS wake_word
            SET id = maximum.id + rows_to_reassign.replacement_offset
            FROM rows_to_reassign
            CROSS JOIN maximum
            WHERE wake_word.ctid = rows_to_reassign.ctid
            '''
        )
        cursor.execute(f'ALTER TABLE {quoted_table} ALTER COLUMN id SET NOT NULL')
        cursor.execute(f'ALTER TABLE {quoted_table} ADD PRIMARY KEY (id)')

        cursor.execute('SELECT pg_get_serial_sequence(%s, %s)', [table_name, 'id'])
        sequence_name = cursor.fetchone()[0]
        if sequence_name is None:
            sequence_name = f'{table_name}_id_seq'
            quoted_sequence = connection.ops.quote_name(sequence_name)
            cursor.execute(f'CREATE SEQUENCE IF NOT EXISTS {quoted_sequence}')
            cursor.execute(
                f'ALTER TABLE {quoted_table} ALTER COLUMN id SET DEFAULT nextval(%s)',
                [sequence_name],
            )
            cursor.execute(f'ALTER SEQUENCE {quoted_sequence} OWNED BY {quoted_table}.id')

        cursor.execute(
            f'''
            SELECT setval(
                %s::regclass,
                COALESCE(MAX(id), 1),
                MAX(id) IS NOT NULL
            )
            FROM {quoted_table}
            ''',
            [sequence_name],
        )


def repair_primary_key(apps, schema_editor) -> None:
    repair_wake_word_primary_key(schema_editor.connection, 'devices_wakeword')


class Migration(migrations.Migration):
    dependencies = [
        ('devices', '0024_devicechatlog_knowledge_references'),
    ]

    operations = [
        migrations.RunPython(repair_primary_key, migrations.RunPython.noop),
    ]
