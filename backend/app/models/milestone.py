import uuid
from sqlalchemy import Column, String, Integer, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.database import Base


class Milestone(Base):
    __tablename__ = "milestones"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    agreement_id = Column(String, ForeignKey("agreements.id"), nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    order = Column(Integer, nullable=False)
    status = Column(String, nullable=False, default="PENDING")
    amount_cents = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    agreement = relationship("Agreement", back_populates="milestones")
    criteria = relationship("AcceptanceCriterion", back_populates="milestone")
    evidence_items = relationship("Evidence", back_populates="milestone")
    approvals = relationship("Approval", back_populates="milestone")
    invoices = relationship("Invoice", back_populates="milestone")
