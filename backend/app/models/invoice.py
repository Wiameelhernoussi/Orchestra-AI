import uuid
from sqlalchemy import Column, String, Integer, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.database import Base


class Invoice(Base):
    __tablename__ = "invoices"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    milestone_id = Column(String, ForeignKey("milestones.id"), nullable=False)
    paypal_invoice_id = Column(String, nullable=True, unique=True)
    paypal_request_id = Column(String, nullable=False, unique=True)
    amount_cents = Column(Integer, nullable=False)
    currency = Column(String, nullable=False, default="USD")
    status = Column(String, nullable=False, default="DRAFT")
    paypal_invoice_url = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    milestone = relationship("Milestone", back_populates="invoices")
