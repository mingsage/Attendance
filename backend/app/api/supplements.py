from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_current_user, require_teacher
from app.core.database import get_db
from app.models.attendance import AttendanceRecord
from app.models.session import AttendanceSession
from app.models.student import Student
from app.models.supplement import SupplementRequest
from app.models.user import User
from app.schemas.supplement import SupplementCreate, SupplementOut

router = APIRouter(prefix="/supplements", tags=["补录申请"])


def _to_out(r):
    student = r.student
    session = r.session
    course_name = ""
    if session and session.course_id:
        from app.models.course import Course
        course = db_get_course(r)
        course_name = course.name if course else ""
    return SupplementOut(
        id=r.id,
        student_id=r.student_id,
        student_name=student.name if student else "",
        student_no=student.student_no if student else "",
        session_id=r.session_id,
        session_info=f"{course_name} {session.date} {session.session_no}" if session else "",
        reason=r.reason,
        status=r.status,
        created_at=r.created_at,
    )


def db_get_course(r):
    # Helper — the session already has a course relationship
    if r.session and r.session.course:
        return r.session.course
    return None


@router.post("", response_model=SupplementOut)
def create_supplement(
    payload: SupplementCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role != "student" or not user.student_id:
        raise HTTPException(status_code=403, detail="仅学生可提交补录申请")
    session = db.get(AttendanceSession, payload.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="考勤活动不存在")
    req = SupplementRequest(
        student_id=user.student_id,
        session_id=payload.session_id,
        reason=payload.reason,
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return _to_out(req)


@router.get("", response_model=list[SupplementOut])
def list_supplements(
    status: str = "pending",
    db: Session = Depends(get_db),
    user: User = Depends(require_teacher),
):
    query = db.query(SupplementRequest).options(
        joinedload(SupplementRequest.student),
        joinedload(SupplementRequest.session).joinedload(AttendanceSession.course),
    )
    if status:
        query = query.filter(SupplementRequest.status == status)
    return [_to_out(r) for r in query.all()]


@router.get("/mine", response_model=list[SupplementOut])
def my_supplements(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role != "student" or not user.student_id:
        raise HTTPException(status_code=403, detail="仅学生可查看")
    records = (
        db.query(SupplementRequest)
        .options(
            joinedload(SupplementRequest.student),
            joinedload(SupplementRequest.session).joinedload(AttendanceSession.course),
        )
        .filter(SupplementRequest.student_id == user.student_id)
        .all()
    )
    return [_to_out(r) for r in records]


@router.put("/{request_id}/approve", response_model=SupplementOut)
def approve_supplement(
    request_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_teacher),
):
    from datetime import datetime, timezone
    req = db.get(SupplementRequest, request_id)
    if not req:
        raise HTTPException(status_code=404, detail="申请不存在")
    req.status = "approved"
    req.reviewed_by = user.id
    req.reviewed_at = datetime.now(timezone.utc)
    # 自动写入考勤记录
    db.add(AttendanceRecord(
        student_id=req.student_id,
        session_id=req.session_id,
        status="success",
        source="supplement",
        message=f"补录通过：{req.reason}",
    ))
    db.commit()
    db.refresh(req)
    return _to_out(req)


@router.put("/{request_id}/reject", response_model=SupplementOut)
def reject_supplement(
    request_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_teacher),
):
    from datetime import datetime, timezone
    req = db.get(SupplementRequest, request_id)
    if not req:
        raise HTTPException(status_code=404, detail="申请不存在")
    req.status = "rejected"
    req.reviewed_by = user.id
    req.reviewed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(req)
    return _to_out(req)
