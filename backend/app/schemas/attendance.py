from datetime import datetime

from pydantic import BaseModel

from app.schemas.student import StudentOut


class AttendanceOut(BaseModel):
    id: int
    timestamp: datetime
    status: str
    confidence: float
    liveness_score: float
    emotion_type: str | None
    course_name: str
    source: str = "camera"
    message: str | None
    student: StudentOut | None = None

    class Config:
        from_attributes = True


class CheckInResponse(BaseModel):
    success: bool
    message: str
    record: AttendanceOut


class RecognizeFace(BaseModel):
    bbox: list[int]       # [x, y, w, h]
    matched: bool
    student: StudentOut | None = None
    confidence: float = 0.0


class RecognizeResponse(BaseModel):
    faces: list[RecognizeFace]
    face_count: int
    matched: bool


class MineResponse(BaseModel):
    attended: list[AttendanceOut]
    missed: list[dict]
    summary: dict


class ManualRecordRequest(BaseModel):
    session_id: int
    student_id: int
    status: str = "success"
    message: str = "手动补录"
