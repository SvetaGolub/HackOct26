"""restore personal reminder_logs and telegram_link_codes

Revision ID: h8b9c0d1e2f3
Revises: g7a8b9c0d1e2

d4 перевёл reminder_logs на chat_id и удалил telegram_link_codes,
но модели и ReminderService снова работают с user_id и кодами привязки.
Общий чат по ТЗ закрыт через payment_occurrences.chat_notified_at.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "h8b9c0d1e2f3"
down_revision: Union[str, Sequence[str], None] = "g7a8b9c0d1e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _columns(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    tables = _tables()

    if "reminder_logs" in tables:
        cols = _columns("reminder_logs")
        if "user_id" not in cols:
            op.drop_table("reminder_logs")
            tables.discard("reminder_logs")

    if "reminder_logs" not in tables:
        op.create_table(
            "reminder_logs",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("occurrence_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column(
                "sent_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("(CURRENT_TIMESTAMP)"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(
                ["occurrence_id"],
                ["payment_occurrences.id"],
                name=op.f("fk_reminder_logs_occurrence_id_payment_occurrences"),
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["user_id"],
                ["users.id"],
                name=op.f("fk_reminder_logs_user_id_users"),
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id", name=op.f("pk_reminder_logs")),
            sa.UniqueConstraint("occurrence_id", "user_id", name="uq_reminder_once"),
        )
        op.create_index(
            op.f("ix_reminder_logs_occurrence_id"),
            "reminder_logs",
            ["occurrence_id"],
            unique=False,
        )

    if "telegram_link_codes" not in _tables():
        op.create_table(
            "telegram_link_codes",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("code_hash", sa.String(length=64), nullable=False),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("(CURRENT_TIMESTAMP)"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(
                ["user_id"],
                ["users.id"],
                name=op.f("fk_telegram_link_codes_user_id_users"),
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id", name=op.f("pk_telegram_link_codes")),
            sa.UniqueConstraint("code_hash", name=op.f("uq_telegram_link_codes_code_hash")),
        )
        op.create_index(
            op.f("ix_telegram_link_codes_user_id"),
            "telegram_link_codes",
            ["user_id"],
            unique=False,
        )


def downgrade() -> None:
    tables = _tables()
    if "telegram_link_codes" in tables:
        op.drop_index(op.f("ix_telegram_link_codes_user_id"), table_name="telegram_link_codes")
        op.drop_table("telegram_link_codes")

    if "reminder_logs" in tables and "user_id" in _columns("reminder_logs"):
        op.drop_index(op.f("ix_reminder_logs_occurrence_id"), table_name="reminder_logs")
        op.drop_table("reminder_logs")
        op.create_table(
            "reminder_logs",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("occurrence_id", sa.Integer(), nullable=False),
            sa.Column("chat_id", sa.String(length=255), nullable=False),
            sa.Column(
                "sent_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("(CURRENT_TIMESTAMP)"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(
                ["occurrence_id"],
                ["payment_occurrences.id"],
                name=op.f("fk_reminder_logs_occurrence_id_payment_occurrences"),
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id", name=op.f("pk_reminder_logs")),
            sa.UniqueConstraint("occurrence_id", "chat_id", name="uq_reminder_once"),
        )
        op.create_index(
            op.f("ix_reminder_logs_occurrence_id"),
            "reminder_logs",
            ["occurrence_id"],
            unique=False,
        )
