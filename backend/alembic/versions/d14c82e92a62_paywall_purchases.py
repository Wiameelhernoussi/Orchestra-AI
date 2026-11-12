"""persist PayPal Sandbox content purchases

Revision ID: d14c82e92a62
Revises: c56e7a9092fb
Create Date: 2026-11-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "d14c82e92a62"
down_revision: Union[str, None] = "c56e7a9092fb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "paywall_purchases",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("offer_id", sa.String(), nullable=False),
        sa.Column("paypal_order_id", sa.String(), nullable=True),
        sa.Column("create_request_id", sa.String(), nullable=False),
        sa.Column("capture_request_id", sa.String(), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("approval_url", sa.String(), nullable=True),
        sa.Column("paypal_capture_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("captured_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("paypal_order_id"),
        sa.UniqueConstraint("create_request_id"),
        sa.UniqueConstraint("capture_request_id"),
    )
    op.create_index("ix_paywall_purchases_user_id", "paywall_purchases", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_paywall_purchases_user_id", table_name="paywall_purchases")
    op.drop_table("paywall_purchases")
