"""persist PayPal invoice timeline and webhook delivery proof

Revision ID: b82fd2a1c417
Revises: a31bfc4429d1
Create Date: 2026-11-09
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "b82fd2a1c417"
down_revision: Union[str, None] = "a31bfc4429d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("invoices", sa.Column("sent_at", sa.DateTime(), nullable=True))
    op.add_column("invoices", sa.Column("last_reminder_at", sa.DateTime(), nullable=True))
    op.add_column("invoices", sa.Column("last_reminder_status", sa.String(), nullable=True))
    op.add_column(
        "webhook_events",
        sa.Column("signature_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "webhook_events",
        sa.Column("duplicate_deliveries", sa.Integer(), nullable=False, server_default="0"),
    )
    op.alter_column("webhook_events", "signature_verified", server_default=None)
    op.alter_column("webhook_events", "duplicate_deliveries", server_default=None)


def downgrade() -> None:
    op.drop_column("webhook_events", "duplicate_deliveries")
    op.drop_column("webhook_events", "signature_verified")
    op.drop_column("invoices", "last_reminder_status")
    op.drop_column("invoices", "last_reminder_at")
    op.drop_column("invoices", "sent_at")
