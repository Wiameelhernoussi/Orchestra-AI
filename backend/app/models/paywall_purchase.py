import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String

from app.database import Base


class PaywallPurchase(Base):
    __tablename__ = "paywall_purchases"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    offer_id = Column(String, nullable=False)
    paypal_order_id = Column(String, nullable=True, unique=True)
    create_request_id = Column(String, nullable=False, unique=True)
    capture_request_id = Column(String, nullable=False, unique=True)
    amount_cents = Column(Integer, nullable=False)
    currency = Column(String, nullable=False, default="USD")
    status = Column(String, nullable=False, default="PENDING")
    approval_url = Column(String, nullable=True)
    paypal_capture_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    captured_at = Column(DateTime, nullable=True)
