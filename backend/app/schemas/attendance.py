from datetime import datetime

from pydantic import BaseModel

from app.schemas.student import StudentOut


class ActivityParticipationItem(BaseModel):
    activity_name: str
    activity_date: str
    confidence: float


class AttendanceOut(BaseModel):
    id: int
    timestamp: datetime
    status: str
    confidence: float
    liveness_score: float
    emotion_type: str | None
    course_name: str
    message: str | None
    photo_url: str | None = None
    student: StudentOut | None = None
    activities: list[ActivityParticipationItem] = []

    class Config:
        from_attributes = True


class CheckInResponse(BaseModel):
    success: bool
    message: str
    record: AttendanceOut


class CheckInResponse(BaseModel):
    success: bool
    message: str
    record: AttendanceOut
