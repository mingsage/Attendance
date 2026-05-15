from datetime import date, datetime
from random import sample
from time import time
from zoneinfo import ZoneInfo

import cv2
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_current_user, require_teacher
from app.core.config import get_settings
from app.core.database import get_db
from app.models.activity import ActivityParticipation
from app.models.attendance import AttendanceRecord
from app.models.emotion import EmotionRecord
from app.models.student import Student
from app.models.user import User
from app.schemas.attendance import (
    ActivityParticipationItem,
    AttendanceOut,
    CheckInResponse,
)
from app.services.emotion_service import emotion_service
from app.services.export_service import build_attendance_workbook
from app.services.face_service import decode_array, face_service
from app.services.image_utils import read_image
from app.services.liveness_service import liveness_service

router = APIRouter(prefix="/attendance", tags=["考勤"])

LIVENESS_ENABLED = True
LIVENESS_ACTIONS = [
    {"code": "smile", "text": "请先保持自然表情，再微笑"},
    {"code": "turn_left", "text": "请先正对摄像头，再向左转头"},
    {"code": "turn_right", "text": "请先正对摄像头，再向右转头"},
    {"code": "open_mouth", "text": "请先闭嘴保持自然，再张嘴"},
]
LIVENESS_SESSION_SECONDS = 120
LIVENESS_CHECKIN_GRACE_SECONDS = 15
LIVENESS_ACTION_STEP_SECONDS = 6
LIVENESS_MIN_ACTION_DELAY_SECONDS = 0.6
LIVENESS_MAX_ACTION_ATTEMPTS = 6


def _query_records(
    db: Session, user: User, keyword: str = "", status: str = "", course_name: str = ""
):
    query = db.query(AttendanceRecord).options(joinedload(AttendanceRecord.student))
    if user.role == "student" and user.student_id:
        query = query.filter(AttendanceRecord.student_id == user.student_id)
    if status:
        query = query.filter(AttendanceRecord.status == status)
    if course_name:
        query = query.filter(AttendanceRecord.course_name == course_name)
    if keyword:
        query = query.join(Student, isouter=True).filter(
            (Student.name.contains(keyword)) | (Student.student_no.contains(keyword))
        )
    return query.order_by(AttendanceRecord.timestamp.desc())


@router.post("/check-in", response_model=CheckInResponse)
async def check_in(
    course_name: str = "默认课程",
    challenge_action: str = Query(
        "", description="活体挑战动作：smile/turn_left/turn_right/open_mouth"
    ),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
<<<<<<< HEAD
    user: User = Depends(require_teacher),
=======
    current_user: User = Depends(require_teacher),
>>>>>>> cf67e4357e420d3df2d4b931b40abe4ad9059f25
):
    image = await read_image(file)
    faces = face_service.detect_faces(image, allow_fallback=False)
    if len(faces) == 0:
        raise HTTPException(
            status_code=400, detail="未检测到人脸，请确保正对摄像头且光线充足"
        )
    if len(faces) > 1:
        box = max(faces, key=lambda f: f[2] * f[3])
    else:
        box = faces[0]
    quality_ok, quality_msg = face_service.check_face_quality(box, image.shape)
    if not quality_ok:
        raise HTTPException(status_code=400, detail=quality_msg)

    probe = face_service.extract_detected_feature(image)
    if probe is None:
        raise HTTPException(
            status_code=400, detail="人脸质量不足，请靠近摄像头并保持正脸"
        )

    # ── 活体检测（反欺骗分析 + 动作验证） ──
    if LIVENESS_ENABLED:
        liveness_score, liveness_threshold, liveness_msg = liveness_service.analyze(
            image, box
        )
        anti_spoofing_ok = liveness_score >= liveness_threshold

<<<<<<< HEAD
        session_ok, session_msg = _consume_verified_session(user.id)
        liveness_passed = anti_spoofing_ok and session_ok
=======
        action_ok = True
        action_msg = ""
        if challenge_action:
            session = _verify_sessions.get(current_user.id if current_user else None)
            if not session or session["expires_at"] < time():
                action_ok = False
                action_msg = "请先刷新活体动作后按顺序完成"
            elif not session.get("completed"):
                remaining = [a["text"] for a in session["actions"][session["step"]:]]
                action_ok = False
                action_msg = f"请按顺序完成全部动作：{' → '.join(remaining)}"
            else:
                face_rows = face_service.detect_sface_rows(image)
                if face_rows:
                    largest = max(face_rows, key=lambda r: float(r[2] * r[3]))
                    action_ok, action_msg = liveness_service.verify_action(
                        image, challenge_action, largest
                    )
                else:
                    action_ok = False
                    action_msg = "无法检测人脸关键点，请确保正对摄像头"
                _clean_session(current_user.id)

        liveness_passed = anti_spoofing_ok and action_ok
>>>>>>> cf67e4357e420d3df2d4b931b40abe4ad9059f25

        if not liveness_passed:
            parts = []
            if not anti_spoofing_ok:
                detail = liveness_msg.replace("活体检测失败：", "")
                parts.append(detail or f"综合得分过低（{liveness_score}）")
            if not session_ok:
                parts.append(session_msg)
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
    success = bool(
        matched_id and confidence >= get_settings().face_threshold and liveness_passed
    )

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

    now = datetime.now(ZoneInfo("Asia/Shanghai"))

    # 去重：同学生同课程的成功记录覆盖更新
    existing = None
    if success and matched_id:
        existing = (
            db.query(AttendanceRecord)
            .filter(
                AttendanceRecord.student_id == matched_id,
                AttendanceRecord.course_name == course_name,
                AttendanceRecord.status == "success",
                func.date(AttendanceRecord.timestamp) == date.today(),
            )
            .order_by(AttendanceRecord.timestamp.desc())
            .first()
        )

    if existing:
        existing.confidence = round(confidence, 3)
        existing.liveness_score = liveness_score
        existing.emotion_type = emotion
        existing.timestamp = now
        existing.message = "考勤已更新：" + message
        record = existing
    else:
        record = AttendanceRecord(
            student_id=matched_id,
            timestamp=now,
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

    # 保存签到照片
    try:
        photo_dir = get_settings().upload_dir / "checkin_photos"
        photo_dir.mkdir(parents=True, exist_ok=True)
        photo_filename = f"checkin_photos/{record.id}.jpg"
        cv2.imwrite(
            str(get_settings().upload_dir / photo_filename),
            image,
            [cv2.IMWRITE_JPEG_QUALITY, 85],
        )
        record.photo_path = photo_filename
        db.commit()
    except Exception:
        pass

    return CheckInResponse(success=success, message=message, record=record)


@router.post("/detect")
async def detect_faces(
    file: UploadFile = File(...),
    _: User = Depends(get_current_user),
):
    """轻量人脸检测：返回相对坐标 + 主脸标记，供前端视频实时画框。"""
    image = await read_image(file)
    faces = face_service.detect_faces(image, allow_fallback=False)
    result = []
    if faces:
        h, w = image.shape[:2]
        largest_idx = max(range(len(faces)), key=lambda i: faces[i][2] * faces[i][3])
        for i, (x, y, fw, fh) in enumerate(faces):
            result.append(
                {
                    "bbox": [x / w, y / h, fw / w, fh / h],
                    "is_primary": i == largest_idx,
                }
            )
    return {"faces": result}


# ── 活体验证会话（内存状态） ──
_verify_sessions: dict[int, dict] = {}
"""
{
  user_id: {
    "actions": [{"code": "smile", "text": "..."}, ...],
    "step": 0,
    "action_state": {},              # 当前 step 的动作基线和开始时间
    "verified": false,               # 全部动作是否已完成
    "verified_at": None | float,      # 最后一个动作完成时间
    "expires_at": float,
  }
}
"""


def _clean_session(user_id: int) -> None:
    _verify_sessions.pop(user_id, None)


def _mark_session_verified(session: dict) -> None:
    now = time()
    session["verified"] = True
    session["verified_at"] = now
    session["expires_at"] = now + LIVENESS_CHECKIN_GRACE_SECONDS


def _step_state(session: dict, step: int, action: str) -> dict:
    state = session.get("action_state") or {}
    if state.get("step") != step or state.get("action") != action:
        state = {
            "step": step,
            "action": action,
            "started_at": time(),
            "baseline": None,
            "attempts": 0,
            "min_mouth_open": 1.0,
            "min_smile": 1.0,
        }
        session["action_state"] = state
    return state


def _action_step_expired(state: dict) -> bool:
    return time() - float(state.get("started_at") or 0) > LIVENESS_ACTION_STEP_SECONDS


def _advance_action_step(session: dict) -> bool:
    session["step"] += 1
    session["action_state"] = {}
    all_done = session["step"] >= len(session["actions"])
    if all_done:
        _mark_session_verified(session)
    return all_done


def _register_action_attempt(user_id: int, state: dict) -> tuple[bool, str]:
    elapsed = time() - float(state.get("started_at") or 0)
    if elapsed < LIVENESS_MIN_ACTION_DELAY_SECONDS:
        return False, "请按提示完成动作"

    state["attempts"] = int(state.get("attempts") or 0) + 1
    if state["attempts"] > LIVENESS_MAX_ACTION_ATTEMPTS:
        _clean_session(user_id)
        return False, "动作尝试过多，请刷新动作"
    return True, ""


def _consume_verified_session(user_id: int) -> tuple[bool, str]:
    """最终签到必须消费一次刚完成的动作会话，避免直接上传视频帧绕过。"""
    session = _verify_sessions.get(user_id)
    if not session:
        return False, "请先完成活体动作"

    now = time()
    if session.get("expires_at", 0) < now:
        _clean_session(user_id)
        return False, "活体动作已超时，请刷新动作"

    actions = session.get("actions", [])
    if not session.get("verified") or session.get("step", 0) < len(actions):
        return False, "请先完成所有活体动作"

    verified_at = session.get("verified_at") or 0
    if now - verified_at > LIVENESS_CHECKIN_GRACE_SECONDS:
        _clean_session(user_id)
        return False, "动作验证已超时，请刷新动作后重试"

    _clean_session(user_id)
    return True, ""


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
        _clean_session(user.id)
        return {
            "passed": False,
            "all_done": False,
            "message": "活体会话已过期，请刷新动作",
        }

    session["expires_at"] = time() + LIVENESS_SESSION_SECONDS  # 续期

    # 检查当前 step 是否匹配客户端的请求
    step = session["step"]
    actions = session["actions"]
    if step >= len(actions):
<<<<<<< HEAD
        if not session.get("verified"):
            _mark_session_verified(session)
=======
        session["completed"] = True
>>>>>>> cf67e4357e420d3df2d4b931b40abe4ad9059f25
        return {"passed": True, "all_done": True, "message": "所有动作已完成"}

    expected = actions[step]["code"]
    if challenge_action != expected:
        session["step"] = 0
        session["turn_baseline"] = None
        session["completed"] = False
        return {"passed": False, "message": f"顺序错误，请重新开始：{actions[0]['text']}"}

    # ── 执行验证 ──
    image = await read_image(file)
    face_rows = face_service.detect_sface_rows(image)
    if not face_rows:
        return {
            "passed": False,
            "all_done": False,
            "message": "无法检测人脸关键点，请确保正对摄像头",
        }

    largest = max(face_rows, key=lambda r: float(r[2] * r[3]))

    if challenge_action in ("turn_left", "turn_right", "turn_head"):
        return _handle_turn_action(session, user.id, challenge_action, largest)

<<<<<<< HEAD
    if challenge_action in ("smile", "open_mouth"):
        return _handle_expression_action(
            session, user.id, challenge_action, image, largest
        )
=======
    passed, msg = liveness_service.verify_action(image, challenge_action, largest)
    if passed:
        session["step"] = step + 1
        all_done = session["step"] >= len(actions)
        if all_done:
            session["completed"] = True
        label = {"smile": "微笑通过", "turn_head": "转头通过", "open_mouth": "张嘴通过"}
        return {"passed": True, "message": msg or label.get(challenge_action, "动作通过"), "all_done": all_done}
>>>>>>> cf67e4357e420d3df2d4b931b40abe4ad9059f25

    return {
        "passed": False,
        "all_done": False,
        "message": f"未知动作：{challenge_action}",
    }


def _handle_turn_action(session: dict, user_id: int, action: str, face_row) -> dict:
    """方向转头检测：必须先正脸建立基线，再按随机指定方向产生位移。"""
    step = session["step"]
    state = _step_state(session, step, action)
    if _action_step_expired(state):
        _clean_session(user_id)
        return {"passed": False, "all_done": False, "message": "动作超时，请刷新动作"}

    x, w = float(face_row[0]), float(face_row[2])
    n_x = float(face_row[8])
    nose_ratio = (n_x - x) / float(w or 1)

    baseline = state.get("baseline")
    if baseline is None:
        if not 0.42 <= nose_ratio <= 0.58:
            return {"passed": False, "all_done": False, "message": "请先正对摄像头"}
        state["baseline"] = nose_ratio
        msg = "请向左转头" if action in ("turn_left", "turn_head") else "请向右转头"
        return {"passed": False, "all_done": False, "message": msg}

    can_try, try_msg = _register_action_attempt(user_id, state)
    if not can_try:
        return {"passed": False, "all_done": False, "message": try_msg}

    delta = nose_ratio - float(baseline)
    if abs(nose_ratio - 0.5) < abs(float(baseline) - 0.5):
        state["baseline"] = nose_ratio

    passed = False
    msg = "请向左转头"
    if action == "turn_left":
        passed = delta > 0.09 and nose_ratio > 0.55
    elif action == "turn_right":
        msg = "请向右转头"
        passed = delta < -0.09 and nose_ratio < 0.45
    else:
        msg = "请左右转头"
        passed = abs(delta) > 0.10

    if passed:
        all_done = _advance_action_step(session)
        return {"passed": True, "message": "转头通过", "all_done": all_done}

    return {"passed": False, "all_done": False, "message": msg}


def _handle_expression_action(
    session: dict,
    user_id: int,
    action: str,
    image,
    face_row,
) -> dict:
    """表情动作检测：先记录自然基线，再要求从基线变化到目标动作。"""
    step = session["step"]
    state = _step_state(session, step, action)
    if _action_step_expired(state):
        _clean_session(user_id)
        return {"passed": False, "all_done": False, "message": "动作超时，请刷新动作"}

    metrics = liveness_service.action_metrics(image, face_row)
    mouth_open = float(metrics["mouth_open"])
    smile = float(metrics["smile"])

    if state.get("baseline") is None:
        state["baseline"] = metrics
        state["min_mouth_open"] = mouth_open
        state["min_smile"] = smile
        msg = "请微笑" if action == "smile" else "请张嘴"
        return {"passed": False, "all_done": False, "message": msg}

    can_try, try_msg = _register_action_attempt(user_id, state)
    if not can_try:
        return {"passed": False, "all_done": False, "message": try_msg}

    state["min_mouth_open"] = min(float(state.get("min_mouth_open", 1.0)), mouth_open)
    state["min_smile"] = min(float(state.get("min_smile", 1.0)), smile)

    if action == "open_mouth":
        baseline = float(state["min_mouth_open"])
        if mouth_open >= max(0.55, baseline + 0.28):
            all_done = _advance_action_step(session)
            return {"passed": True, "message": "张嘴通过", "all_done": all_done}
        if baseline > 0.35:
            return {"passed": False, "all_done": False, "message": "请先闭嘴保持自然"}
        return {"passed": False, "all_done": False, "message": "请张嘴"}

    if action == "smile":
        if smile >= 1.0 and float(state["min_smile"]) < 0.5:
            all_done = _advance_action_step(session)
            return {"passed": True, "message": "微笑通过", "all_done": all_done}
        if float(state["min_smile"]) >= 0.5:
            return {"passed": False, "all_done": False, "message": "请先保持自然表情"}
        return {"passed": False, "all_done": False, "message": "请微笑"}

    return {"passed": False, "all_done": False, "message": f"未知动作：{action}"}


async def _verify_action_fallback(challenge_action: str, file: UploadFile) -> dict:
    """无会话时的降级单次验证（兼容旧前端 / session 过期）。"""
    return {"passed": False, "all_done": False, "message": "活体会话已过期，请刷新动作"}


@router.get("/liveness-challenge")
def liveness_challenge(user: User = Depends(get_current_user)):
    """返回多个随机挑战动作，前端按 step 依次验证。"""
    if not LIVENESS_ENABLED:
        session["completed"] = True
        return {"enabled": False, "actions": [], "expires_in": 0}

    num = min(3, len(LIVENESS_ACTIONS))
    selected = sample(LIVENESS_ACTIONS, num)

    _verify_sessions[user.id] = {
        "actions": selected,
        "step": 0,
        "action_state": {},
        "verified": False,
        "verified_at": None,
        "expires_at": time() + LIVENESS_SESSION_SECONDS,
    }

    return {
        "enabled": True,
        "actions": selected,
        "expires_in": LIVENESS_SESSION_SECONDS,
    }


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
    records = _query_records(db, user, keyword, status, course_name).limit(limit).all()

    # 为每条记录附上学生的活动参与信息
    student_ids = {r.student_id for r in records if r.student_id}
    if student_ids:
        participations = (
            db.query(ActivityParticipation)
            .filter(ActivityParticipation.student_id.in_(student_ids))
            .order_by(ActivityParticipation.activity_date.desc())
            .all()
        )
        acts_by_student: dict[int, list[ActivityParticipationItem]] = {}
        for p in participations:
            acts_by_student.setdefault(p.student_id, []).append(
                ActivityParticipationItem(
                    activity_name=p.activity_name,
                    activity_date=p.activity_date.isoformat(),
                    confidence=round(p.confidence, 3),
                )
            )
        for r in records:
            r.activities = acts_by_student.get(r.student_id, [])
    else:
        for r in records:
            r.activities = []

    # 课次信息：每个课程按日期排序编号，统计每课次签到人数
    courses = {r.course_name for r in records if r.course_name}
    if courses:
        course_dates = {}
        for cn in courses:
            dates = (
                db.query(func.date(AttendanceRecord.timestamp))
                .filter(AttendanceRecord.course_name == cn)
                .distinct()
                .order_by(func.date(AttendanceRecord.timestamp))
                .all()
            )
            course_dates[cn] = [d[0] for d in dates]
        for r in records:
            if r.course_name and r.timestamp:
                r_date = r.timestamp.strftime("%Y-%m-%d")
                dates = course_dates.get(r.course_name, [])
                if r_date in dates:
                    r.session_num = dates.index(r_date) + 1
                    r.session_count = (
                        db.query(AttendanceRecord)
                        .filter(
                            AttendanceRecord.course_name == r.course_name,
                            AttendanceRecord.status == "success",
                            func.date(AttendanceRecord.timestamp) == r_date,
                        )
                        .count()
                    )

    return records


@router.get("/export")
def export_records(
    keyword: str = "",
    status: str = "",
    course_name: str = "",
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    stream = build_attendance_workbook(
        _query_records(db, user, keyword, status, course_name).all()
    )
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
    records = (
        db.query(AttendanceRecord)
        .filter(AttendanceRecord.id.in_(payload.record_ids))
        .all()
    )
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
