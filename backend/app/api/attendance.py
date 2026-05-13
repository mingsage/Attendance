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
    {"code": "smile", "text": "请微笑后完成考勤"},
    {"code": "turn_left", "text": "请向左转头后完成考勤"},
    {"code": "turn_right", "text": "请向右转头后完成考勤"},
    {"code": "open_mouth", "text": "请张嘴后完成考勤"},
]


def _query_records(
    db: Session, user: User, keyword: str = "", status: str = ""
):
    query = db.query(AttendanceRecord).options(
        joinedload(AttendanceRecord.student)
    )
    if user.role == "student" and user.student_id:
        query = query.filter(
            AttendanceRecord.student_id == user.student_id
        )
    if status:
        query = query.filter(AttendanceRecord.status == status)
    if keyword:
        query = query.join(Student, isouter=True).filter(
            (Student.name.contains(keyword))
            | (Student.student_no.contains(keyword))
        )
    return query.order_by(AttendanceRecord.timestamp.desc())


@router.post("/check-in", response_model=CheckInResponse)
async def check_in(
    course_name: str = "默认课程",
    challenge_action: str = "",
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    image = await read_image(file)

    # 检测人脸（使用 InsightFace SCRFD）
    details = face_service.detect_face_details(image)
    if not details:
        raise HTTPException(
            status_code=400, detail="未检测到人脸，请确保正对摄像头且光线充足"
        )
    if len(details) > 1:
        raise HTTPException(
            status_code=400, detail="检测到多张人脸，请确保画面中只有您一人"
        )

    face_info = details[0]
    box = face_info["bbox"]
    keypoints = face_info.get("kps")

    quality_ok, quality_msg = face_service.check_face_quality(box, image.shape)
    if not quality_ok:
        raise HTTPException(status_code=400, detail=quality_msg)

    # 特征提取（复用已检测到的人脸嵌入）
    probe = face_info.get("embedding")
    if probe is None:
        probe = face_service.extract_detected_feature(image)
    if probe is None:
        raise HTTPException(
            status_code=400, detail="人脸质量不足，请靠近摄像头并保持正脸"
        )

    # ── 活体检测 ──
    action_failed = False
    if LIVENESS_ENABLED:
        liveness_score, liveness_message = liveness_service.analyze(
            image, face_box=box, keypoints=keypoints
        )
        # 动作验证
        if challenge_action and box:
            action_ok, action_msg = liveness_service.verify_action(
                image, challenge_action, box, keypoints
            )
            if not action_ok:
                action_failed = True
                liveness_message = action_msg
    else:
        liveness_score, liveness_message = 1.0, "活体检测已关闭"

    # ── 情绪分析 ──
    emotion, emotion_confidence = emotion_service.analyze(image, box)

    # ── 人脸识别 ──
    candidates = [
        (student.id, decode_array(student.face_encoding), student.face_image_path)
        for student in db.query(Student)
        .filter(Student.face_encoding.isnot(None))
        .all()
    ]
    matched_id, confidence = face_service.identify(image, probe, candidates)

    liveness_passed = (
        (not LIVENESS_ENABLED)
        or (liveness_score >= liveness_service.BASE_THRESHOLD and not action_failed)
    )
    success = bool(
        matched_id
        and confidence >= get_settings().face_threshold
        and liveness_passed
    )

    if success:
        message = f"考勤成功：{confidence:.1%} 置信度匹配"
        if emotion != "neutral":
            message += f"，检测到情绪：{emotion}"
    elif action_failed:
        message = liveness_message
    elif matched_id and confidence < get_settings().face_threshold:
        message = (
            f"匹配置信度 {confidence:.1%} 低于阈值，请靠近摄像头重新拍摄"
        )
    elif LIVENESS_ENABLED and liveness_score < liveness_service.BASE_THRESHOLD:
        message = liveness_message
    else:
        message = "识别失败，请重新对准摄像头；如多次失败请联系管理员补充正面照片"

    record = AttendanceRecord(
        student_id=matched_id,
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
        db.add(
            EmotionRecord(
                student_id=matched_id,
                emotion_type=emotion,
                confidence=emotion_confidence,
                source="attendance",
                timestamp=record.timestamp,
            )
        )
    db.commit()
    db.refresh(record)
    return CheckInResponse(
        success=success, message=message, record=record
    )


@router.get("/liveness-challenge")
def liveness_challenge(_: User = Depends(get_current_user)):
    action = choice(LIVENESS_ACTIONS)
    if not LIVENESS_ENABLED:
        return {
            "enabled": False,
            "action": "disabled",
            "text": "活体检测已关闭",
            "expires_in": 0,
        }
    return {
        "enabled": True,
        "action": action["code"],
        "text": action["text"],
        "expires_in": 15,
    }


@router.get("/liveness-settings")
def get_liveness_settings(_: User = Depends(get_current_user)):
    return {"enabled": LIVENESS_ENABLED}


@router.put("/liveness-settings")
def update_liveness_settings(
    enabled: bool, _: User = Depends(get_current_user)
):
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
    return (
        _query_records(db, user, keyword, status).limit(limit).all()
    )


@router.get("/export")
def export_records(
    keyword: str = "",
    status: str = "",
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    stream = build_attendance_workbook(
        _query_records(db, user, keyword, status).all()
    )
    filename = f"attendance-{datetime.now().strftime('%Y%m%d%H%M%S')}.xlsx"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return StreamingResponse(
        stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers,
    )
