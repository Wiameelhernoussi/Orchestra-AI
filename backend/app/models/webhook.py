import uuid
from sqlalchemy import Column, String, DateTime, Text
from datetime import datetime, timezone
from app.database import Base


class WebhookEvent(Base):
    __tablename__ = "webhook_events"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    paypal_event_id = Column(String, nullable=False, unique=True)  # idempotency
    event_type = Column(String, nullable=False)
    resource_id = Column(String, nullable=True)
    raw_payload = Column(Text, nullable=False)
    processed = Column(String, nullable=False, default="pending")  # pending, processed, failed
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
