import uuid
from sqlalchemy import Column, String, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.database import Base


class Approval(Base):
    __tablename__ = "approvals"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    milestone_id = Column(String, ForeignKey("milestones.id"), nullable=False)
    approved_by = Column(String, ForeignKey("users.id"), nullable=False)
    decision = Column(String, nullable=False)  # "approved" or "rejected"
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    milestone = relationship("Milestone", back_populates="approvals")
