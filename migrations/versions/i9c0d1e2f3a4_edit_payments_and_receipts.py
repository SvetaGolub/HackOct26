"""support editing payments and attached receipts

Revision ID: i9c0d1e2f3a4
Revises: h8b9c0d1e2f3
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import MEDIUMTEXT


revision: str = "i9c0d1e2f3a4"
down_revision: Union[str, Sequence[str], None] = "h8b9c0d1e2f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("payment_occurrences")}
    if "receipt_name" not in columns:
        op.add_column("payment_occurrences", sa.Column("receipt_name", sa.String(length=255), nullable=True))
    if "receipt_data_url" not in columns:
        op.add_column(
            "payment_occurrences",
            sa.Column("receipt_data_url", sa.Text().with_variant(MEDIUMTEXT(), "mysql"), nullable=True),
        )


def downgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("payment_occurrences")}
    if "receipt_data_url" in columns:
        op.drop_column("payment_occurrences", "receipt_data_url")
    if "receipt_name" in columns:
        op.drop_column("payment_occurrences", "receipt_name")
