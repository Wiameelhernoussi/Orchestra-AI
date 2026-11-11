"""mark previously stored PayPal webhooks as verified

Revision ID: c56e7a9092fb
Revises: b82fd2a1c417
Create Date: 2026-11-09
"""
from typing import Sequence, Union

from alembic import op

revision: str = "c56e7a9092fb"
down_revision: Union[str, None] = "b82fd2a1c417"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "UPDATE webhook_events SET signature_verified = TRUE "
        "WHERE signature_verified = FALSE"
    )


def downgrade() -> None:
    pass
