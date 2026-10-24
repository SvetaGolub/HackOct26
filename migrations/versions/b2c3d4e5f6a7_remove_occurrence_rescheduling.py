"""remove occurrence rescheduling and index payment queries

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("payment_occurrences") as batch_op:
        batch_op.drop_index("ix_occurrence_dept_due")
        batch_op.drop_index(op.f("ix_payment_occurrences_due_date"))
        batch_op.drop_index(op.f("ix_payment_occurrences_is_paid"))
        batch_op.drop_constraint(
            op.f("fk_payment_occurrences_rescheduled_by_users"),
            type_="foreignkey",
        )
        batch_op.drop_column("original_due_date")
        batch_op.drop_column("rescheduled_by")
        batch_op.drop_column("reschedule_reason")
        batch_op.create_index(
            "ix_occurrence_due_paid", ["due_date", "is_paid"], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table("payment_occurrences") as batch_op:
        batch_op.drop_index("ix_occurrence_due_paid")
        batch_op.add_column(sa.Column("original_due_date", sa.Date(), nullable=True))
        batch_op.add_column(sa.Column("rescheduled_by", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("reschedule_reason", sa.String(500), nullable=True))
        batch_op.create_foreign_key(
            op.f("fk_payment_occurrences_rescheduled_by_users"),
            "users",
            ["rescheduled_by"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index(
            op.f("ix_payment_occurrences_due_date"), ["due_date"], unique=False
        )
        batch_op.create_index(
            op.f("ix_payment_occurrences_is_paid"), ["is_paid"], unique=False
        )
        batch_op.create_index(
            "ix_occurrence_dept_due", ["department_id", "due_date"], unique=False
        )

    op.execute(
        "UPDATE payment_occurrences SET original_due_date = due_date "
        "WHERE original_due_date IS NULL"
    )
    with op.batch_alter_table("payment_occurrences") as batch_op:
        batch_op.alter_column(
            "original_due_date",
            existing_type=sa.Date(),
            nullable=False,
        )
