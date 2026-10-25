"""support recurrence options and shared departments

Revision ID: j0d1e2f3a4b5
Revises: i9c0d1e2f3a4
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "j0d1e2f3a4b5"
down_revision: Union[str, Sequence[str], None] = "i9c0d1e2f3a4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("recurring_payments")}
    if "interval_days" not in columns:
        op.add_column("recurring_payments", sa.Column("interval_days", sa.Integer(), nullable=True))
    if "departments" not in sa.inspect(op.get_bind()).get_table_names():
        op.create_table(
            "departments",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.UniqueConstraint("name", name="uq_department_name"),
        )
        existing = op.get_bind().execute(sa.text(
            "SELECT DISTINCT department FROM recurring_payments "
            "WHERE department IS NOT NULL AND TRIM(department) <> ''"
        )).scalars()
        for name in existing:
            op.get_bind().execute(
                sa.text("INSERT INTO departments (name) VALUES (:name)"),
                {"name": name},
            )


def downgrade() -> None:
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    if "departments" in tables:
        op.drop_table("departments")
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("recurring_payments")}
    if "interval_days" in columns:
        op.drop_column("recurring_payments", "interval_days")
