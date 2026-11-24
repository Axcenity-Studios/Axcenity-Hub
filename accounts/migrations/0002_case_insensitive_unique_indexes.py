"""Unique indexes on LOWER(username) and LOWER(email) (see accounts/integrity.py).

The first operation checks for existing rows that differ only in case and stops the
migration, naming each one, if it finds any. It never changes data.
"""

from django.db import migrations

from accounts.integrity import (
    CASE_INSENSITIVE_INDEXES,
    check_no_case_conflicts,
    create_index_sql,
    drop_index_sql,
)


def check_existing_rows(apps, schema_editor):
    check_no_case_conflicts(schema_editor.connection)


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0001_initial"),
        ("auth", "0012_alter_user_first_name_max_length"),
        ("account", "0009_emailaddress_unique_primary_email"),
    ]

    operations = [
        migrations.RunPython(check_existing_rows, migrations.RunPython.noop),
        *[
            migrations.RunSQL(create_index_sql(*index), drop_index_sql(index[0]))
            for index in CASE_INSENSITIVE_INDEXES
        ],
    ]
