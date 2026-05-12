from sqlalchemy import LargeBinary, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Student(Base):
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    student_no: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(64), index=True)
    class_name: Mapped[str] = mapped_column(String(64), index=True)
    gender: Mapped[str | None] = mapped_column(String(16), nullable=True)
    face_encoding: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    face_sample_count: Mapped[int] = mapped_column(default=0)
    face_image_path: Mapped[str | None] = mapped_column(String(255), nullable=True)

    user = relationship("User", back_populates="student", uselist=False)
    attendance_records = relationship("AttendanceRecord", back_populates="student")
    emotion_records = relationship("EmotionRecord", back_populates="student")
    activities = relationship("ActivityParticipation", back_populates="student")

    @property
    def has_face(self) -> bool:
        """供接口响应序列化使用，表示该学生是否已录入人脸特征。"""

        return self.face_encoding is not None
