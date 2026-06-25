from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('knowledge_base', '0009_knowledge_document_index_fields'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            ALTER TABLE knowledge_base_knowledgebase
                ADD COLUMN IF NOT EXISTS chunk_overlap smallint NOT NULL DEFAULT 50,
                ADD COLUMN IF NOT EXISTS chunk_size smallint NOT NULL DEFAULT 500,
                ADD COLUMN IF NOT EXISTS retrieval_top_n smallint NOT NULL DEFAULT 5;

            ALTER TABLE knowledge_base_knowledgedocument
                ADD COLUMN IF NOT EXISTS chunk_count integer NOT NULL DEFAULT 0,
                ADD COLUMN IF NOT EXISTS index_error text NOT NULL DEFAULT '',
                ADD COLUMN IF NOT EXISTS index_model varchar(128) NOT NULL DEFAULT '',
                ADD COLUMN IF NOT EXISTS index_status varchar(16) NOT NULL DEFAULT 'pending',
                ADD COLUMN IF NOT EXISTS indexed_at timestamp with time zone NULL;
            """,
            reverse_sql=migrations.RunSQL.noop,
            state_operations=[],
        ),
    ]
