"""rename user email column to login

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, Sequence[str], None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_names(table: str) -> set[str]:
    bind = op.get_bind()
    return {col["name"] for col in sa.inspect(bind).get_columns(table)}


def _index_names(table: str) -> set[str]:
    bind = op.get_bind()
    return {idx["name"] for idx in sa.inspect(bind).get_indexes(table) if idx["name"]}


def upgrade() -> None:
    user_cols = _column_names("users")
    user_indexes = _index_names("users")

    if "email" in user_cols and "login" not in user_cols:
        if "uq_users_email" in user_indexes:
            op.drop_constraint("uq_users_email", "users", type_="unique")
        # CHANGE COLUMN is reliable on MySQL 8 for rename + keep type/nullability
        op.execute(
            "ALTER TABLE users CHANGE COLUMN email login VARCHAR(255) NOT NULL"
        )
        op.create_unique_constraint("uq_users_login", "users", ["login"])
        user_cols = _column_names("users")
        user_indexes = _index_names("users")

    if "telegram_id" not in user_cols:
        op.add_column("users", sa.Column("telegram_id", sa.BigInteger(), nullable=True))
        op.create_unique_constraint("uq_users_telegram_id", "users", ["telegram_id"])

    audit_cols = _column_names("audit_logs")
    if "actor_email" in audit_cols and "actor_login" not in audit_cols:
        op.execute(
            "ALTER TABLE audit_logs CHANGE COLUMN actor_email actor_login VARCHAR(255) NULL"
        )


def downgrade() -> None:
    user_cols = _column_names("users")
    user_indexes = _index_names("users")

    audit_cols = _column_names("audit_logs")
    if "actor_login" in audit_cols and "actor_email" not in audit_cols:
        op.execute(
            "ALTER TABLE audit_logs CHANGE COLUMN actor_login actor_email VARCHAR(255) NULL"
        )

    if "telegram_id" in user_cols:
        if "uq_users_telegram_id" in user_indexes:
            op.drop_constraint("uq_users_telegram_id", "users", type_="unique")
        op.drop_column("users", "telegram_id")

    user_cols = _column_names("users")
    user_indexes = _index_names("users")
    if "login" in user_cols and "email" not in user_cols:
        if "uq_users_login" in user_indexes:
            op.drop_constraint("uq_users_login", "users", type_="unique")
        op.execute(
            "ALTER TABLE users CHANGE COLUMN login email VARCHAR(255) NOT NULL"
        )
        op.create_unique_constraint("uq_users_email", "users", ["email"])
