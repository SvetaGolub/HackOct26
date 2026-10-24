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


def upgrade() -> None:
    op.drop_constraint("uq_users_email", "users", type_="unique")
    op.alter_column(
        "users",
        "email",
        new_column_name="login",
        existing_type=sa.String(length=255),
        existing_nullable=False,
    )
    op.create_unique_constraint("uq_users_login", "users", ["login"])


def downgrade() -> None:
    op.drop_constraint("uq_users_login", "users", type_="unique")
    op.alter_column(
        "users",
        "login",
        new_column_name="email",
        existing_type=sa.String(length=255),
        existing_nullable=False,
    )
    op.create_unique_constraint("uq_users_email", "users", ["email"])
