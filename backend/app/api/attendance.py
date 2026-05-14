from datetime import date, datetime
from random import choice
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_current_user, require_teacher
from app.core.config import get_settings
from app.core.database import get_db
from app.models.attendance import AttendanceRecord
from app.models.emotion import EmotionRecord
from app.models.session import AttendanceSession
from app.models.group import Group
from app.models.student import Student
from app.models.user import User
from app.schemas.attendance import (
    AttendanceOut,
    CheckInResponse,
    ManualRecordRequest,
    MineResponse,
    RecognizeFace,
    RecognizeResponse,
)
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


def _query_records(db, user, keyword="", status=""):
    query = db.query(AttendanceRecord).options(joinedload(AttendanceRecord.student))
    if user.role == "student" and user.student_id:
        query = query.filter(AttendanceRecord.student_id == user.student_id)
    if status:
        query = query.filter(AttendanceRecord.status == status)
    if keyword:
        query = query.join(Student, isouter=True).filter(
            (Student.name.contains(keyword)) | (Student.student_no.contains(keyword))
        )
    return query.order_by(AttendanceRecord.timestamp.desc())


# ── 轻量识别（不写库）───────────────────────────────────

@router.post("/recognize", response_model=RecognizeResponse)
async def recognize(
    file: UploadFile = File(...),
    _: User = Depends(get_current_user),
):
    """轻量识别：检测人脸 + 比对，不写库，用于前端实时预览。"""
    from app.core.database import SessionLocal
    image = await read_image(file)
    details = face_service.detect_face_details(image)
    if not details:
        return RecognizeResponse(faces=[], face_count=0, matched=False)

    db_local = SessionLocal()
    try:
        candidates = [
            (student.id, decode_array(student.face_encoding), student.face_image_path)
            for student in db_local.query(Student).filter(Student.face_encoding.isnot(None)).all()
        ]
    finally:
        db_local.close()

    faces: list[RecognizeFace] = []
    matched_any = False
    for face_info in details:
        bbox = list(face_info["bbox"])
        probe = face_info.get("embedding")
        if probe is None:
            faces.append(RecognizeFace(bbox=bbox, matched=False))
            continue
        matched_id, confidence = face_service.identify(image, probe, candidates)
        if matched_id and confidence >= get_settings().face_threshold:
            matched_any = True
            faces.append(RecognizeFace(bbox=bbox, matched=True, student=_get_student_out(db_local, matched_id), confidence=confidence))
        else:
            faces.append(RecognizeFace(bbox=bbox, matched=False, confidence=confidence))
    return RecognizeResponse(faces=faces, face_count=len(faces), matched=matched_any)


def _get_student_out(db, student_id):
    from app.schemas.student import StudentOut
    s = db.get(Student, student_id)
    if not s:
        return None
    return StudentOut(
        id=s.id, student_no=s.student_no, name=s.name, class_name=s.class_name,
        gender=s.gender, grade=s.grade, major=s.major,
        has_face=s.face_encoding is not None,
        face_sample_count=s.face_sample_count or 0,
        face_image_path=s.face_image_path, face_image_url=None,
        face_status=s.face_status,
    )


# ── 正式提交考勤（活体 + 写入）──────────────────────────

@router.post("/check-in", response_model=CheckInResponse)
async def check_in(
    course_name: str = "默认课程",
    session_id: int | None = None,
    challenge_action: str = "",
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    image = await read_image(file)

    details = face_service.detect_face_details(image)
    if not details:
        raise HTTPException(status_code=400, detail="未检测到人脸，请确保正对摄像头且光线充足")
    if len(details) > 1:
        raise HTTPException(status_code=400, detail="检测到多张人脸，请确保画面中只有您一人")

    face_info = details[0]
    box = face_info["bbox"]
    keypoints = face_info.get("kps")

    quality_ok, quality_msg = face_service.check_face_quality(box, image.shape)
    if not quality_ok:
        raise HTTPException(status_code=400, detail=quality_msg)

    probe = face_info.get("embedding")
    if probe is None:
        probe = face_service.extract_detected_feature(image)
    if probe is None:
        raise HTTPException(status_code=400, detail="人脸质量不足，请靠近摄像头并保持正脸")

    # 活体检测
    action_failed = False
    if LIVENESS_ENABLED:
        liveness_score, liveness_message = liveness_service.analyze(image, face_box=box, keypoints=keypoints)
        if challenge_action and box:
            action_ok, action_msg = liveness_service.verify_action(image, challenge_action, box, keypoints)
            if not action_ok:
                action_failed = True
                liveness_message = action_msg
    else:
        liveness_score, liveness_message = 1.0, "活体检测已关闭"

    # 情绪分析
    emotion, emotion_confidence = emotion_service.analyze(image, box)

    # 人脸识别
    candidates = [
        (student.id, decode_array(student.face_encoding), student.face_image_path)
        for student in db.query(Student).filter(Student.face_encoding.isnot(None)).all()
    ]
    matched_id, confidence = face_service.identify(image, probe, candidates)

    liveness_passed = (not LIVENESS_ENABLED) or (liveness_score >= liveness_service.BASE_THRESHOLD and not action_failed)
    success = bool(matched_id and confidence >= get_settings().face_threshold and liveness_passed)

    if success:
        message = f"考勤成功：{confidence:.1%} 置信度匹配"
        if emotion != "neutral":
            message += f"，检测到情绪：{emotion}"
    elif action_failed:
        message = liveness_message
    elif matched_id and confidence < get_settings().face_threshold:
        message = f"匹配置信度 {confidence:.1%} 低于阈值，请靠近摄像头重新拍摄"
    elif LIVENESS_ENABLED and liveness_score < liveness_service.BASE_THRESHOLD:
        message = liveness_message
    else:
        message = "识别失败，请重新对准摄像头；如多次失败请联系管理员补充正面照片"

    record = AttendanceRecord(
        student_id=matched_id,
        session_id=session_id,
        timestamp=datetime.now(ZoneInfo("Asia/Shanghai")),
        status="success" if success else "failed",
        confidence=round(confidence, 3),
        liveness_score=liveness_score,
        emotion_type=emotion,
        course_name=course_name,
        source="camera",
        message=message,
    )
    db.add(record)
    if success and matched_id:
        db.add(EmotionRecord(
            student_id=matched_id, emotion_type=emotion,
            confidence=emotion_confidence, source="attendance",
            timestamp=record.timestamp,
        ))
    db.commit()
    db.refresh(record)
    return CheckInResponse(success=success, message=message, record=record)


# ── 活体挑战 / 设置 ─────────────────────────────────────

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


# ── 记录查询 ────────────────────────────────────────────

@router.get("/records", response_model=list[AttendanceOut])
def records(
    keyword: str = "",
    status: str = "",
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return _query_records(db, user, keyword, status).limit(limit).all()


@router.get("/records/mine", response_model=MineResponse)
def my_records(
    course_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """学生查看自己的考勤（含缺签）。"""
    if user.role != "student" or not user.student_id:
        raise HTTPException(status_code=403, detail="仅学生可查看")
    student_id = user.student_id

    # 已签
    attended_query = db.query(AttendanceRecord).filter(
        AttendanceRecord.student_id == student_id, AttendanceRecord.status == "success"
    )
    if course_id:
        session_ids = [s.id for s in db.query(AttendanceSession.id).filter(
            AttendanceSession.course_id == course_id
        ).all()]
        attended_query = attended_query.filter(AttendanceRecord.session_id.in_([r[0] for r in session_ids]))
    attended = attended_query.all()

    # 学生所在群组 → 该去的 session
    student_obj = db.get(Student, student_id)
    attended_session_ids = {r.session_id for r in attended if r.session_id}
    missed_list = []
    if student_obj:
        for group in student_obj.groups:
            sessions = db.query(AttendanceSession).filter(
                AttendanceSession.group_id == group.id
            )
            if course_id:
                sessions = sessions.filter(AttendanceSession.course_id == course_id)
            for s in sessions.all():
                if s.id not in attended_session_ids:
                    missed_list.append({
                        "session_id": s.id,
                        "date": str(s.date),
                        "session_no": s.session_no,
                        "type": s.type,
                        "course_name": s.course.name if s.course else "",
                    })

    total = len(attended) + len(missed_list)
    rate = f"{len(attended) / total * 100:.1f}%" if total > 0 else "0%"
    return MineResponse(
        attended=attended,
        missed=missed_list,
        summary={"total": total, "attended": len(attended), "missed": len(missed_list), "rate": rate},
    )


# ── 删除 ────────────────────────────────────────────────

@router.delete("/records/{record_id}")
def delete_record(
    record_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_teacher),
):
    rec = db.get(AttendanceRecord, record_id)
    if not rec:
        raise HTTPException(status_code=404, detail="记录不存在")
    db.delete(rec)
    db.commit()
    return {"ok": True}


@router.post("/records/batch-delete")
def batch_delete_records(
    payload: dict,  # { ids: [1, 2, 3] }
    db: Session = Depends(get_db),
    _: User = Depends(require_teacher),
):
    ids = payload.get("ids", [])
    if not ids:
        raise HTTPException(status_code=400, detail="请提供要删除的记录ID")
    db.query(AttendanceRecord).filter(AttendanceRecord.id.in_(ids)).delete(synchronize_session=False)
    db.commit()
    return {"ok": True, "deleted_count": len(ids)}


# ── 手动补录 ────────────────────────────────────────────

@router.post("/records/manual", response_model=AttendanceOut)
def manual_record(
    payload: ManualRecordRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_teacher),
):
    student = db.get(Student, payload.student_id)
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")
    record = AttendanceRecord(
        student_id=payload.student_id,
        session_id=payload.session_id,
        timestamp=datetime.now(ZoneInfo("Asia/Shanghai")),
        status=payload.status,
        source="manual",
        message=payload.message,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


# ── 导出 ────────────────────────────────────────────────

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
    return StreamingResponse(stream, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers=headers)
