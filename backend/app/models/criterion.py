import uuid
from sqlalchemy import Column, String, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.database import Base


class AcceptanceCriterion(Base):
    __tablename__ = "acceptance_criteria"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    milestone_id = Column(String, ForeignKey("milestones.id"), nullable=False)
    description = Column(Text, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    milestone = relationship("Milestone", back_populates="criteria")
