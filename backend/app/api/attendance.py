from datetime import datetime
from random import sample
from time import time
from zoneinfo import ZoneInfo

import cv2
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_current_user, require_teacher
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
    {"code": "turn_head", "text": "请左右转头后完成考勤"},
    {"code": "open_mouth", "text": "请张嘴后完成考勤"},
]


def _query_records(db: Session, user: User, keyword: str = "", status: str = "", course_name: str = ""):
    query = db.query(AttendanceRecord).options(joinedload(AttendanceRecord.student))
    if user.role == "student" and user.student_id:
        query = query.filter(AttendanceRecord.student_id == user.student_id)
    if status:
        query = query.filter(AttendanceRecord.status == status)
    if course_name:
        query = query.filter(AttendanceRecord.course_name == course_name)
    if keyword:
        query = query.join(Student, isouter=True).filter((Student.name.contains(keyword)) | (Student.student_no.contains(keyword)))
    return query.order_by(AttendanceRecord.timestamp.desc())


@router.post("/check-in", response_model=CheckInResponse)
async def check_in(
    course_name: str = "默认课程",
    challenge_action: str = Query("", description="活体挑战动作：smile/turn_left/turn_right/open_mouth"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: User = Depends(require_teacher),
):
    image = await read_image(file)
    faces = face_service.detect_faces(image, allow_fallback=False)
    if len(faces) == 0:
        raise HTTPException(status_code=400, detail="未检测到人脸，请确保正对摄像头且光线充足")
    if len(faces) > 1:
        box = max(faces, key=lambda f: f[2] * f[3])
    else:
        box = faces[0]
    quality_ok, quality_msg = face_service.check_face_quality(box, image.shape)
    if not quality_ok:
        raise HTTPException(status_code=400, detail=quality_msg)

    probe = face_service.extract_detected_feature(image)
    if probe is None:
        raise HTTPException(status_code=400, detail="人脸质量不足，请靠近摄像头并保持正脸")

    # ── 活体检测（反欺骗分析 + 动作验证） ──
    if LIVENESS_ENABLED:
        liveness_score, liveness_threshold, liveness_msg = liveness_service.analyze(image)
        anti_spoofing_ok = liveness_score >= liveness_threshold

        action_ok = True
        action_msg = ""
        if challenge_action:
            face_rows = face_service.detect_sface_rows(image)
            if face_rows:
                largest = max(face_rows, key=lambda r: float(r[2] * r[3]))
                action_ok, action_msg = liveness_service.verify_action(
                    image, challenge_action, largest
                )
            else:
                action_ok = False
                action_msg = "无法检测人脸关键点，请确保正对摄像头"

        liveness_passed = anti_spoofing_ok and action_ok

        if not liveness_passed:
            parts = []
            if not anti_spoofing_ok:
                detail = liveness_msg.replace("活体检测失败：", "")
                parts.append(detail or f"综合得分过低（{liveness_score}）")
            if not action_ok:
                parts.append(action_msg)
            liveness_result_msg = "活体检测失败：" + "、".join(parts)
        else:
            liveness_result_msg = "活体检测通过"
    else:
        liveness_score = 1.0
        liveness_threshold = 0.0
        liveness_passed = True
        liveness_result_msg = "活体检测已关闭"

    # ── 情绪分析 ──
    emotion, emotion_confidence = emotion_service.analyze(image, box)

    # ── 人脸识别 ──
    candidates = [
        (student.id, decode_array(student.face_encoding), student.face_image_path)
        for student in db.query(Student).filter(Student.face_encoding.isnot(None)).all()
    ]
    matched_id, confidence = face_service.identify(image, probe, candidates)
    success = bool(matched_id and confidence >= get_settings().face_threshold and liveness_passed)

    # ── 构建消息 ──
    if success:
        message = f"考勤成功：{confidence:.1%} 置信度匹配"
        if emotion != "neutral":
            message += f"，检测到情绪：{emotion}"
    else:
        message = "识别失败，请重新对准摄像头；如多次失败请联系管理员补充正面照片"
        if matched_id and confidence < get_settings().face_threshold:
            message = f"匹配置信度 {confidence:.1%} 低于阈值，请靠近摄像头重新拍摄"

    if not liveness_passed:
        message = liveness_result_msg

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
        db.add(EmotionRecord(student_id=matched_id, emotion_type=emotion, confidence=emotion_confidence, source="attendance", timestamp=record.timestamp))
    db.commit()
    db.refresh(record)

    # 保存签到照片
    try:
        photo_dir = get_settings().upload_dir / "checkin_photos"
        photo_dir.mkdir(parents=True, exist_ok=True)
        photo_filename = f"checkin_photos/{record.id}.jpg"
        cv2.imwrite(str(get_settings().upload_dir / photo_filename), image, [cv2.IMWRITE_JPEG_QUALITY, 85])
        record.photo_path = photo_filename
        db.commit()
    except Exception:
        pass

    return CheckInResponse(success=success, message=message, record=record)


# ── 活体验证会话（内存状态） ──
_verify_sessions: dict[int, dict] = {}
"""
{
  user_id: {
    "actions": [{"code": "smile", "text": "..."}, ...],
    "step": 0,
    "turn_baseline": None | float,   # 转头检测的基线鼻位
    "expires_at": float,
  }
}
"""


def _clean_session(user_id: int) -> None:
    _verify_sessions.pop(user_id, None)


@router.post("/verify-action")
async def verify_action(
    challenge_action: str = Query(..., description="当前挑战动作 code"),
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
):
    """有状态动作验证：支持多动作串行 + 转头基线对比防照片欺骗。

    返回格式：
      {"passed": true/false, "message": "...", "all_done": true/false}
    前端按 step 依次验证，all_done=true 后调 check-in。
    """
    if not challenge_action or not LIVENESS_ENABLED:
        return {"passed": True, "all_done": True, "message": "无需验证"}

    # 获取会话
    session = _verify_sessions.get(user.id)
    if not session or session["expires_at"] < time():
        # 会话过期或缺失 → 走无状态单次验证（兼容旧流程）
        return await _verify_action_fallback(challenge_action, file)

    session["expires_at"] = time() + 120  # 续期

    # 检查当前 step 是否匹配客户端的请求
    step = session["step"]
    actions = session["actions"]
    if step >= len(actions):
        _clean_session(user.id)
        return {"passed": True, "all_done": True, "message": "所有动作已完成"}

    expected = actions[step]["code"]
    if challenge_action != expected:
        return {"passed": False, "message": f"请完成：{actions[step]['text']}"}

    # ── 执行验证 ──
    image = await read_image(file)
    face_rows = face_service.detect_sface_rows(image)
    if not face_rows:
        haar_faces = face_service.detect_faces(image, allow_fallback=False)
        if not haar_faces:
            return {"passed": False, "message": "未检测到人脸"}
        return {"passed": True, "message": "无法验证动作"}

    largest = max(face_rows, key=lambda r: float(r[2] * r[3]))

    # 转头用基线对比（防照片摇晃欺骗）
    if challenge_action == "turn_head":
        return _handle_turn_head(session, user.id, largest)

    passed, msg = liveness_service.verify_action(image, challenge_action, largest)
    if passed:
        session["step"] = step + 1
        all_done = session["step"] >= len(actions)
        if all_done:
            _clean_session(user.id)
        label = {"smile": "微笑通过", "turn_head": "转头通过", "open_mouth": "张嘴通过"}
        return {"passed": True, "message": msg or label.get(challenge_action, "动作通过"), "all_done": all_done}

    return {"passed": False, "message": msg}


def _handle_turn_head(session: dict, user_id: int, face_row) -> dict:
    """转头检测：对比当前鼻位与基线，必须发生位移（照片做不到）。"""
    _, _, w = int(face_row[0]), int(face_row[1]), int(face_row[2])
    n_x = int(face_row[8])
    nose_ratio = n_x / float(w or 1)  # 0.5=正脸, <0.5=偏右, >0.5=偏左

    baseline = session.get("turn_baseline")
    if baseline is None:
        session["turn_baseline"] = nose_ratio
        return {"passed": False, "message": "请左右转头"}

    if abs(nose_ratio - baseline) > 0.10:
        session["step"] += 1
        session["turn_baseline"] = None
        all_done = session["step"] >= len(session["actions"])
        if all_done:
            _clean_session(user_id)
        return {"passed": True, "message": "转头通过", "all_done": all_done}

    return {"passed": False, "message": "请左右转头"}


async def _verify_action_fallback(challenge_action: str, file: UploadFile) -> dict:
    """无会话时的降级单次验证（兼容旧前端 / session 过期）。"""
    image = await read_image(file)
    face_rows = face_service.detect_sface_rows(image)
    if not face_rows:
        haar_faces = face_service.detect_faces(image, allow_fallback=False)
        if not haar_faces:
            return {"passed": False, "message": "未检测到人脸"}
        return {"passed": True, "message": "无法验证动作"}

    largest = max(face_rows, key=lambda r: float(r[2] * r[3]))
    passed, msg = liveness_service.verify_action(image, challenge_action, largest)
    # 降级模式下单次验证通过即 all_done
    return {"passed": passed, "message": msg, "all_done": passed}


@router.get("/liveness-challenge")
def liveness_challenge(user: User = Depends(get_current_user)):
    """返回多个随机挑战动作，前端按 step 依次验证。"""
    if not LIVENESS_ENABLED:
        _clean_session(user.id)
        return {"enabled": False, "actions": [], "expires_in": 0}

    num = min(3, len(LIVENESS_ACTIONS))
    selected = sample(LIVENESS_ACTIONS, num)

    _verify_sessions[user.id] = {
        "actions": selected,
        "step": 0,
        "turn_baseline": None,
        "expires_at": time() + 120,
    }

    return {"enabled": True, "actions": selected, "expires_in": 60}


@router.get("/liveness-settings")
def get_liveness_settings(_: User = Depends(get_current_user)):
    return {"enabled": LIVENESS_ENABLED}


@router.put("/liveness-settings", dependencies=[Depends(require_teacher)])
def update_liveness_settings(enabled: bool, _: User = Depends(get_current_user)):
    global LIVENESS_ENABLED
    LIVENESS_ENABLED = enabled
    return {"enabled": LIVENESS_ENABLED}


@router.get("/records", response_model=list[AttendanceOut])
def records(
    keyword: str = "",
    status: str = "",
    course_name: str = "",
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return _query_records(db, user, keyword, status, course_name).limit(limit).all()


@router.get("/export")
def export_records(
    keyword: str = "",
    status: str = "",
    course_name: str = "",
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    stream = build_attendance_workbook(_query_records(db, user, keyword, status, course_name).all())
    filename = f"attendance-{datetime.now().strftime('%Y%m%d%H%M%S')}.xlsx"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return StreamingResponse(
        stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers,
    )


@router.delete("/records/{record_id}", dependencies=[Depends(require_teacher)])
def delete_record(record_id: int, db: Session = Depends(get_db)):
    """删除单条考勤记录及对应的签到照片和情绪记录。"""
    record = db.get(AttendanceRecord, record_id)
    if not record:
        raise HTTPException(status_code=404, detail="记录不存在")
    if record.photo_path and not record.photo_path.startswith("group_photos/"):
        try:
            photo = get_settings().upload_dir / record.photo_path
            if photo.exists():
                photo.unlink()
        except Exception:
            pass
    # 删除关联的情绪记录
    db.query(EmotionRecord).filter(
        EmotionRecord.student_id == record.student_id,
        EmotionRecord.timestamp == record.timestamp,
        EmotionRecord.source == "attendance",
    ).delete()
    db.delete(record)
    db.commit()
    return {"ok": True}


class _BatchDeleteRequest(BaseModel):
    record_ids: list[int]


@router.post("/records/batch-delete", dependencies=[Depends(require_teacher)])
def batch_delete_records(payload: _BatchDeleteRequest, db: Session = Depends(get_db)):
    """批量删除考勤记录及对应的签到照片和情绪记录。"""
    records = db.query(AttendanceRecord).filter(AttendanceRecord.id.in_(payload.record_ids)).all()
    for record in records:
        if record.photo_path and not record.photo_path.startswith("group_photos/"):
            try:
                photo = get_settings().upload_dir / record.photo_path
                if photo.exists():
                    photo.unlink()
            except Exception:
                pass
        # 删除关联的情绪记录
        db.query(EmotionRecord).filter(
            EmotionRecord.student_id == record.student_id,
            EmotionRecord.timestamp == record.timestamp,
            EmotionRecord.source == "attendance",
        ).delete()
        db.delete(record)
    db.commit()
    return {"deleted_count": len(records)}
