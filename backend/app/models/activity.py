from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ActivityParticipation(Base):
    __tablename__ = "activity_participation"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"))
    activity_name: Mapped[str] = mapped_column(String(128), index=True)
    activity_date: Mapped[date] = mapped_column(Date, index=True)
    recognized: Mapped[bool] = mapped_column(Boolean, default=True)
    confidence: Mapped[float] = mapped_column(default=0)

    student = relationship("Student", back_populates="activities")
