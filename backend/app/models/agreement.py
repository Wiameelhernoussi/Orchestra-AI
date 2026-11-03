import uuid
from sqlalchemy import Column, String, Integer, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.database import Base


class Agreement(Base):
    __tablename__ = "agreements"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String, nullable=False, default="DRAFT")
    total_amount_cents = Column(Integer, nullable=False)
    currency = Column(String, nullable=False, default="USD")
    client_org_id = Column(String, ForeignKey("organizations.id"), nullable=False)
    provider_org_id = Column(String, ForeignKey("organizations.id"), nullable=True)
    created_by = Column(String, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    milestones = relationship("Milestone", back_populates="agreement", order_by="Milestone.order")
    audit_logs = relationship("AuditLog", back_populates="agreement")
