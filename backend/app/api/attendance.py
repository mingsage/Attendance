from datetime import datetime
from random import choice
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.database import get_db
from app.models.attendance import AttendanceRecord
from app.models.emotion import EmotionRecord
from app.models.student import Student
from app.models.user import User
from app.schemas.attendance import AttendanceOut, CheckInResponse
from app.services.emotion_service import emotion_service
from app.services.export_service import build_attendance_workbook
from app.services.face_service import decode_array, face_service
from app.services.image_utils import read_image
from app.services.liveness_service import liveness_service


router = APIRouter(prefix="/attendance", tags=["考勤"])

LIVENESS_ENABLED = True
LIVENESS_ACTIONS = [
    {"code": "blink", "text": "请眨眼后完成考勤"},
    {"code": "turn_left", "text": "请向左转头后完成考勤"},
    {"code": "turn_right", "text": "请向右转头后完成考勤"},
    {"code": "open_mouth", "text": "请张嘴后完成考勤"},
]


def _query_records(db: Session, user: User, keyword: str = "", status: str = ""):
    query = db.query(AttendanceRecord).options(joinedload(AttendanceRecord.student))
    if user.role == "student" and user.student_id:
        query = query.filter(AttendanceRecord.student_id == user.student_id)
    if status:
        query = query.filter(AttendanceRecord.status == status)
    if keyword:
        query = query.join(Student, isouter=True).filter((Student.name.contains(keyword)) | (Student.student_no.contains(keyword)))
    return query.order_by(AttendanceRecord.timestamp.desc())


@router.post("/check-in", response_model=CheckInResponse)
async def check_in(
    course_name: str = "默认课程",
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    image = await read_image(file)
    faces = face_service.detect_faces(image, allow_fallback=False)
    if len(faces) == 0:
        raise HTTPException(status_code=400, detail="未检测到人脸，请确保正对摄像头且光线充足")
    if len(faces) > 1:
        raise HTTPException(status_code=400, detail="检测到多张人脸，请确保画面中只有您一人")

    box = faces[0]
    quality_ok, quality_msg = face_service.check_face_quality(box, image.shape)
    if not quality_ok:
        raise HTTPException(status_code=400, detail=quality_msg)

    probe = face_service.extract_detected_feature(image)
    if probe is None:
        raise HTTPException(status_code=400, detail="人脸质量不足，请靠近摄像头并保持正脸")

    if LIVENESS_ENABLED:
        liveness_score, liveness_message = liveness_service.analyze(image)
    else:
        liveness_score, liveness_message = 1.0, "活体检测已关闭"

    emotion, emotion_confidence = emotion_service.analyze(image, faces[0])
    candidates = [
        (student.id, decode_array(student.face_encoding), student.face_image_path)
        for student in db.query(Student).filter(Student.face_encoding.isnot(None)).all()
    ]
    matched_id, confidence = face_service.identify(image, probe, candidates)
    liveness_passed = (not LIVENESS_ENABLED) or liveness_score >= 0.30
    success = bool(matched_id and confidence >= get_settings().face_threshold and liveness_passed)
    if success:
        message = f"考勤成功：{confidence:.1%} 置信度匹配"
        if emotion != "neutral":
            message += f"，检测到情绪：{emotion}"
    else:
        message = "识别失败，请重新对准摄像头；如多次失败请联系管理员补充正面照片"
        if matched_id and confidence < get_settings().face_threshold:
            message = f"匹配置信度 {confidence:.1%} 低于阈值，请靠近摄像头重新拍摄"
    if LIVENESS_ENABLED and liveness_score < 0.30:
        message = liveness_message

    record = AttendanceRecord(
        student_id=matched_id,  # 即使匹配失败也保存匹配到的学生，前端可显示完整信息
        timestamp=datetime.now(ZoneInfo("Asia/Shanghai")),
        status="success" if success else "failed",
        confidence=round(confidence, 3),
        liveness_score=liveness_score,
        emotion_type=emotion,
        course_name=course_name,
        message=message,
    )
    db.add(record)
    if success and matched_id:
        db.add(EmotionRecord(student_id=matched_id, emotion_type=emotion, confidence=emotion_confidence, source="attendance", timestamp=record.timestamp))
    db.commit()
    db.refresh(record)
    return CheckInResponse(success=success, message=message, record=record)


@router.get("/liveness-challenge")
def liveness_challenge(_: User = Depends(get_current_user)):
    action = choice(LIVENESS_ACTIONS)
    if not LIVENESS_ENABLED:
        return {"enabled": False, "action": "disabled", "text": "活体检测已关闭", "expires_in": 0}
    return {"enabled": True, "action": action["code"], "text": action["text"], "expires_in": 15}


@router.get("/liveness-settings")
def get_liveness_settings(_: User = Depends(get_current_user)):
    return {"enabled": LIVENESS_ENABLED}


@router.put("/liveness-settings")
def update_liveness_settings(enabled: bool, _: User = Depends(get_current_user)):
    global LIVENESS_ENABLED
    LIVENESS_ENABLED = enabled
    return {"enabled": LIVENESS_ENABLED}


@router.get("/records", response_model=list[AttendanceOut])
def records(
    keyword: str = "",
    status: str = "",
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return _query_records(db, user, keyword, status).limit(limit).all()


@router.get("/export")
def export_records(
    keyword: str = "",
    status: str = "",
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    stream = build_attendance_workbook(_query_records(db, user, keyword, status).all())
    filename = f"attendance-{datetime.now().strftime('%Y%m%d%H%M%S')}.xlsx"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return StreamingResponse(
        stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers,
    )
