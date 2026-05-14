from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.config import get_settings


class AttendanceRecord(Base):
    __tablename__ = "attendance_records"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    student_id: Mapped[int | None] = mapped_column(ForeignKey("students.id"), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    status: Mapped[str] = mapped_column(String(20), index=True)
    confidence: Mapped[float] = mapped_column(Float, default=0)
    liveness_score: Mapped[float] = mapped_column(Float, default=0)
    emotion_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    course_name: Mapped[str] = mapped_column(String(128), default="默认课程")
    message: Mapped[str | None] = mapped_column(String(255), nullable=True)
    photo_path: Mapped[str | None] = mapped_column(String(512), nullable=True)

    student = relationship("Student", back_populates="attendance_records")

    @property
    def photo_url(self) -> str | None:
        if self.photo_path:
            return f"/uploads/{self.photo_path}"
        return None
