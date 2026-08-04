from __future__ import annotations

from importlib import import_module

from django.db import connection
from django.test import TestCase


class WakeWordPrimaryKeyRepairTests(TestCase):
    def test_repair_reassigns_duplicate_ids_without_touching_other_tenant_rows(self):
        table_name = 'wake_word_primary_key_repair'
        bindings_table_name = 'wake_word_primary_key_repair_devices'
        quoted_bindings_table = connection.ops.quote_name(bindings_table_name)
        sequence_name = 'wake_word_primary_key_repair_id_seq'
        quoted_table = connection.ops.quote_name(table_name)
        quoted_sequence = connection.ops.quote_name(sequence_name)
        repair = import_module(
            'apps.devices.migrations.0025_repair_wakeword_primary_key'
        ).repair_wake_word_primary_key

        with connection.cursor() as cursor:
            cursor.execute(f'CREATE TEMPORARY SEQUENCE {quoted_sequence}')
            cursor.execute(
                f'''
                CREATE TEMPORARY TABLE {quoted_table} (
                    id bigint NOT NULL DEFAULT nextval('{sequence_name}'),
                    text varchar(16) NOT NULL,
                    tenant_id bigint NOT NULL,
                    created_at timestamptz NOT NULL
                ) ON COMMIT PRESERVE ROWS
                '''
            )
            cursor.execute(
                f'''
                CREATE TEMPORARY TABLE {quoted_bindings_table} (
                    wake_word_id bigint NOT NULL,
                    device_id bigint NOT NULL
                ) ON COMMIT PRESERVE ROWS
                '''
            )
            cursor.execute(
                f'''
                INSERT INTO {quoted_table} (id, text, tenant_id, created_at)
                VALUES
                    (7, '你好小灰', 1, '2026-07-07T03:13:06+00:00'),
                    (7, '你好小灵', 1, '2026-08-04T16:42:53+00:00'),
                    (8, '你好小智', 2, '2026-08-04T16:43:00+00:00')
                '''
            )
            cursor.execute(
                f'INSERT INTO {quoted_bindings_table} (wake_word_id, device_id) VALUES (7, 101)'
            )

        repair(connection, table_name)

        with connection.cursor() as cursor:
            cursor.execute(f'SELECT id, text, tenant_id FROM {quoted_table} ORDER BY text')
            rows = cursor.fetchall()
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
            has_primary_key = cursor.fetchone()[0]
            cursor.execute(
                f'''
                INSERT INTO {quoted_table} (text, tenant_id, created_at)
                VALUES ('你好小德', 2, NOW())
                RETURNING id
                '''
            )
            next_id = cursor.fetchone()[0]
            cursor.execute(
                f'SELECT wake_word_id, device_id FROM {quoted_bindings_table}'
            )
            bindings = cursor.fetchall()

        row_by_text = {text: (row_id, tenant_id) for row_id, text, tenant_id in rows}
        self.assertEqual(row_by_text['你好小灰'], (7, 1))
        self.assertEqual(row_by_text['你好小智'], (8, 2))
        self.assertNotEqual(row_by_text['你好小灵'][0], 7)
        self.assertEqual(row_by_text['你好小灵'][1], 1)
        self.assertEqual(len({row_id for row_id, _, _ in rows}), len(rows))
        self.assertTrue(has_primary_key)
        self.assertGreater(next_id, max(row_id for row_id, _, _ in rows))
        self.assertEqual(bindings, [(7, 101)])

    def test_repair_skips_a_table_that_already_has_a_primary_key(self):
        table_name = 'wake_word_primary_key_healthy'
        quoted_table = connection.ops.quote_name(table_name)
        repair = import_module(
            'apps.devices.migrations.0025_repair_wakeword_primary_key'
        ).repair_wake_word_primary_key

        with connection.cursor() as cursor:
            cursor.execute(
                f'''
                CREATE TEMPORARY TABLE {quoted_table} (
                    id bigint PRIMARY KEY,
                    text varchar(16) NOT NULL
                ) ON COMMIT PRESERVE ROWS
                '''
            )
            cursor.execute(
                f"INSERT INTO {quoted_table} (id, text) VALUES (7, '健康唤醒词')"
            )

        repair(connection, table_name)

        with connection.cursor() as cursor:
            cursor.execute(f'SELECT id, text FROM {quoted_table}')
            rows = cursor.fetchall()

        self.assertEqual(rows, [(7, '健康唤醒词')])
