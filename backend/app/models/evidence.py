import uuid
from sqlalchemy import Column, String, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.database import Base


class Evidence(Base):
    __tablename__ = "evidence"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    milestone_id = Column(String, ForeignKey("milestones.id"), nullable=False)
    submitted_by = Column(String, ForeignKey("users.id"), nullable=False)
    evidence_type = Column(String, nullable=False)  # "text", "link", "file"
    content = Column(Text, nullable=True)  # text content or URL
    file_path = Column(String, nullable=True)  # local file path for uploads
    ai_report = Column(Text, nullable=True)  # JSON string of Evidence Agent output
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    milestone = relationship("Milestone", back_populates="evidence_items")
