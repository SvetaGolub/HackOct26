"""track reminders sent to the shared Telegram chat

Revision ID: g7a8b9c0d1e2
Revises: f6a7b8c9d0e1
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "g7a8b9c0d1e2"
down_revision: Union[str, Sequence[str], None] = "f6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("payment_occurrences")}
    if "chat_notified_at" not in columns:
        op.add_column(
            "payment_occurrences",
            sa.Column("chat_notified_at", sa.DateTime(timezone=True), nullable=True),
        )


def downgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("payment_occurrences")}
    if "chat_notified_at" in columns:
        op.drop_column("payment_occurrences", "chat_notified_at")
