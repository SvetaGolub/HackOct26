"""store department and employee labels on payments

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, Sequence[str], None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("recurring_payments", sa.Column("department", sa.String(length=255), nullable=True))
    op.add_column("recurring_payments", sa.Column("employee", sa.String(length=255), nullable=True))
    op.add_column("payment_occurrences", sa.Column("department", sa.String(length=255), nullable=True))
    op.add_column("payment_occurrences", sa.Column("employee", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("payment_occurrences", "employee")
    op.drop_column("payment_occurrences", "department")
    op.drop_column("recurring_payments", "employee")
    op.drop_column("recurring_payments", "department")
