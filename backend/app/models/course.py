from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(128))
    semester: Mapped[str] = mapped_column(String(32))
    school_year: Mapped[str] = mapped_column(String(16))
    teacher_id: Mapped[int] = mapped_column(ForeignKey("users.id"))

    sessions = relationship("AttendanceSession", back_populates="course")
