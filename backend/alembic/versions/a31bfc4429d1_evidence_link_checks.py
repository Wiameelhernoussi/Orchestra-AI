"""store deterministic evidence link checks

Revision ID: a31bfc4429d1
Revises: 3d96362b57ce
Create Date: 2026-11-04
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "a31bfc4429d1"
down_revision: Union[str, None] = "3d96362b57ce"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("evidence", sa.Column("link_checks", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("evidence", "link_checks")
