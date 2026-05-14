from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_teacher
from app.core.database import get_db
from app.models.course import Course
from app.models.session import AttendanceSession
from app.models.user import User
from app.schemas.course import CourseCreate, CourseOut, CourseUpdate, SessionCreate, SessionOut

router = APIRouter(prefix="/courses", tags=["课程"])

# ── Session 子路由 ──
session_router = APIRouter(prefix="/sessions", tags=["考勤活动"])


def _course_out(c):
    return CourseOut(id=c.id, name=c.name, semester=c.semester, school_year=c.school_year)


@router.get("", response_model=list[CourseOut])
def list_courses(
    db: Session = Depends(get_db),
    user: User = Depends(require_teacher),
):
    courses = db.query(Course).filter(Course.teacher_id == user.id).all()
    return [_course_out(c) for c in courses]


@router.post("", response_model=CourseOut)
def create_course(
    payload: CourseCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_teacher),
):
    course = Course(**payload.model_dump(), teacher_id=user.id)
    db.add(course)
    db.commit()
    db.refresh(course)
    return _course_out(course)


@router.put("/{course_id}", response_model=CourseOut)
def update_course(
    course_id: int,
    payload: CourseUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_teacher),
):
    course = db.query(Course).filter(Course.id == course_id, Course.teacher_id == user.id).first()
    if not course:
        raise HTTPException(status_code=404, detail="课程不存在")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(course, k, v)
    db.commit()
    db.refresh(course)
    return _course_out(course)


@router.delete("/{course_id}")
def delete_course(
    course_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_teacher),
):
    course = db.query(Course).filter(Course.id == course_id, Course.teacher_id == user.id).first()
    if not course:
        raise HTTPException(status_code=404, detail="课程不存在")
    db.delete(course)
    db.commit()
    return {"ok": True}


# ── Session ──

@session_router.post("", response_model=SessionOut)
def create_session(
    payload: SessionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_teacher),
):
    session = AttendanceSession(**payload.model_dump())
    db.add(session)
    db.commit()
    db.refresh(session)
    return _session_out(session, db)


@session_router.get("/active", response_model=list[SessionOut])
def active_sessions(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from datetime import date
    sessions = db.query(AttendanceSession).filter(
        AttendanceSession.date == date.today()
    ).all()
    return [_session_out(s, db) for s in sessions]


@session_router.get("/{session_id}", response_model=SessionOut)
def get_session(
    session_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    session = db.get(AttendanceSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="考勤活动不存在")
    return _session_out(session, db)


def _session_out(session, db):
    course = db.get(Course, session.course_id) if session.course_id else None
    from app.models.group import Group
    group = db.get(Group, session.group_id) if session.group_id else None
    return SessionOut(
        id=session.id,
        course_id=session.course_id,
        course_name=course.name if course else "",
        date=str(session.date),
        session_no=session.session_no,
        type=session.type,
        group_id=session.group_id,
        group_name=group.name if group else "",
        created_at=session.created_at,
    )
