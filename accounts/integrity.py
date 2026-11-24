"""Case-insensitive uniqueness of usernames and emails, as database indexes.

Migration 0002 creates unique indexes on LOWER(username) and LOWER(email) for
`auth_user`, and on LOWER(email) for allauth's `account_emailaddress`. The SQL is the
same on SQLite and PostgreSQL. (SQLite's LOWER folds ASCII letters only; usernames are
ASCII by their validator, and allauth stores emails lower-cased already.)

Before creating them, the migration looks for rows that already differ only in case.
If it finds any, it stops and names every conflicting record. It never deletes,
renames or merges an account: that's a person's decision, made by hand.
"""

from dataclasses import dataclass

# (index name, table, column, partial condition): the indexes migration 0002 creates.
CASE_INSENSITIVE_INDEXES = [
    ("accounts_user_username_ci_uniq", "auth_user", "username", ""),
    ("accounts_user_email_ci_uniq", "auth_user", "email", "email <> ''"),
    ("accounts_emailaddress_email_ci_uniq", "account_emailaddress", "email", ""),
]


@dataclass(frozen=True)
class CaseConflict:
    """Rows of one table whose `column` values are equal once lower-cased."""

    table: str
    column: str
    key: str  # the lower-cased value they share
    rows: tuple[tuple[int, str], ...]  # (primary key, value as stored)

    def describe(self) -> str:
        rows = ", ".join(f"id {pk} {value!r}" for pk, value in self.rows)
        return f"{self.table}.{self.column} {self.key!r}: {rows}"


class CaseDuplicatesFound(RuntimeError):
    """Existing rows break case-insensitive uniqueness; nothing was changed."""

    def __init__(self, conflicts: list[CaseConflict]) -> None:
        self.conflicts = conflicts
        lines = "\n".join(f"  - {conflict.describe()}" for conflict in conflicts)
        super().__init__(
            "Can't add the case-insensitive unique indexes: these records differ only in "
            f"case.\n{lines}\nRename or remove the duplicates by hand (nothing was deleted "
            "or merged), then run migrate again."
        )


def create_index_sql(name: str, table: str, column: str, condition: str) -> str:
    where = f" WHERE {condition}" if condition else ""
    return f"CREATE UNIQUE INDEX {name} ON {table} (LOWER({column})){where}"


def drop_index_sql(name: str) -> str:
    return f"DROP INDEX IF EXISTS {name}"


def find_case_conflicts(connection) -> list[CaseConflict]:
    """Every group of rows the indexes would reject, read-only. Table and column names
    come from CASE_INSENSITIVE_INDEXES, never from input."""
    conflicts = []
    with connection.cursor() as cursor:
        for _name, table, column, condition in CASE_INSENSITIVE_INDEXES:
            where = f" WHERE {condition}" if condition else ""
            cursor.execute(
                f"SELECT id, {column}, LOWER({column}) FROM {table}{where} "
                f"ORDER BY LOWER({column}), id"
            )
            groups: dict[str, list[tuple[int, str]]] = {}
            for pk, value, key in cursor.fetchall():
                groups.setdefault(key, []).append((pk, value))
            conflicts += [
                CaseConflict(table, column, key, tuple(rows))
                for key, rows in groups.items()
                if len(rows) > 1
            ]
    return conflicts


def check_no_case_conflicts(connection) -> None:
    """Raise CaseDuplicatesFound naming every conflict; return quietly when there are none."""
    conflicts = find_case_conflicts(connection)
    if conflicts:
        raise CaseDuplicatesFound(conflicts)
