from sqlalchemy import func
from sqlalchemy.orm import Session

from datetime import datetime
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.activity import ActivityParticipation
from app.models.attendance import AttendanceRecord
from app.models.emotion import EmotionRecord
from app.models.student import Student
from app.models.user import User
from app.schemas.statistics import ActivityDetailItem, ActivityItem, CountItem
from app.services.export_service import build_activity_workbook, build_attendance_stats_workbook


router = APIRouter(prefix="/statistics", tags=["统计"])


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    total_students = db.query(Student).count()
    success_count = db.query(AttendanceRecord).filter(AttendanceRecord.status == "success").count()
    failed_count = db.query(AttendanceRecord).filter(AttendanceRecord.status == "failed").count()
    activity_count = db.query(ActivityParticipation).count()
    return {
        "total_students": total_students,
        "success_count": success_count,
        "failed_count": failed_count,
        "activity_count": activity_count,
    }


@router.get("/emotion", response_model=list[CountItem])
def emotion_stats(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    query = db.query(EmotionRecord.emotion_type, func.count(EmotionRecord.id))
    if user.role == "student":
        if not user.student_id:
            return []
        query = query.filter(
            EmotionRecord.student_id == user.student_id,
            EmotionRecord.source == "attendance",
        )
    rows = query.group_by(EmotionRecord.emotion_type).all()
    return [CountItem(name=name, value=count) for name, count in rows]


@router.get("/course-list")
def course_list(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    rows = db.query(AttendanceRecord.course_name).distinct().order_by(AttendanceRecord.course_name).all()
    return [row[0] for row in rows]


@router.get("/course-dates")
def course_dates(course_name: str = "", db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    query = db.query(func.strftime("%Y-%m-%d", AttendanceRecord.timestamp).label("d")).distinct()
    if course_name:
        query = query.filter(AttendanceRecord.course_name == course_name)
    rows = query.order_by("d").all()
    return [row[0] for row in rows]


@router.get("/attendance-stats", response_model=list[ActivityItem])
def attendance_stats(course_name: str = "", attendance_date: str = "", db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    # 去重规则：同一学生同一天同一门课只算 1 次
    if attendance_date:
        # 选了具体日期：显示所有学生，标记是否签到
        checkin_ids = {
            row[0] for row in
            db.query(AttendanceRecord.student_id)
            .filter(
                AttendanceRecord.status == "success",
                func.strftime("%Y-%m-%d", AttendanceRecord.timestamp) == attendance_date,
            )
            .filter(AttendanceRecord.course_name.contains(course_name) if course_name else True)
            .distinct()
            .all()
        }
        all_students = db.query(Student.student_no, Student.name, Student.class_name, Student.id).order_by(Student.id).all()
        return [
            ActivityItem(id=sid, student_no=no, name=name, class_name=klass, count=1 if sid in checkin_ids else 0)
            for no, name, klass, sid in all_students
        ]

    # 未选日期：按 (日期, 课程) 去重后计出勤天数
    distinct_key = func.strftime("%Y-%m-%d", AttendanceRecord.timestamp).op("||")(AttendanceRecord.course_name)
    count_col = func.count(func.distinct(distinct_key))
    query = (
        db.query(Student.id, Student.student_no, Student.name, Student.class_name, count_col)
        .join(AttendanceRecord, AttendanceRecord.student_id == Student.id)
        .filter(AttendanceRecord.status == "success")
    )
    if course_name:
        query = query.filter(AttendanceRecord.course_name.contains(course_name))
    rows = query.group_by(Student.id).order_by(count_col.desc()).all()
    return [ActivityItem(id=sid, student_no=no, name=name, class_name=klass, count=count) for sid, no, name, klass, count in rows]


@router.get("/attendance-export")
def attendance_export(course_name: str = "", db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    if not course_name:
        raise HTTPException(status_code=400, detail="请先选择课程")
    # 获取该课程的所有日期
    date_rows = (
        db.query(func.strftime("%Y-%m-%d", AttendanceRecord.timestamp).label("d"))
        .filter(AttendanceRecord.course_name.contains(course_name))
        .distinct()
        .order_by("d")
        .all()
    )
    dates = [row[0] for row in date_rows]
    if not dates:
        raise HTTPException(status_code=404, detail="该课程暂无考勤记录")

    # 获取每个学生在每个日期的签到情况
    all_students = db.query(Student.id, Student.name, Student.class_name).order_by(Student.id).all()

    # 一次查询所有签到记录（替代原来的 N+1 循环）
    checkin_rows = (
        db.query(
            AttendanceRecord.student_id,
            func.strftime("%Y-%m-%d", AttendanceRecord.timestamp).label("d"),
        )
        .filter(
            AttendanceRecord.status == "success",
            AttendanceRecord.course_name.contains(course_name),
            func.strftime("%Y-%m-%d", AttendanceRecord.timestamp).in_(dates),
        )
        .distinct()
        .all()
    )
    checkin_map: dict[int, set[str]] = {}
    for sid, d in checkin_rows:
        checkin_map.setdefault(sid, set()).add(d)

    students = []
    for sid, name, klass in all_students:
        checked_dates = checkin_map.get(sid, set())
        students.append({
            "name": name,
            "class_name": klass,
            "checkin": {d: d in checked_dates for d in dates},
        })

    safe_name = quote(course_name, safe="")
    filename = f"attendance-stats-{safe_name}-{datetime.now().strftime('%Y%m%d%H%M%S')}.xlsx"
    stream = build_attendance_stats_workbook(students, dates)
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return StreamingResponse(
        stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers,
    )


@router.get("/activity", response_model=list[ActivityItem])
def activity_stats(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    rows = (
        db.query(Student.student_no, Student.name, Student.class_name, func.count(ActivityParticipation.id))
        .join(ActivityParticipation, ActivityParticipation.student_id == Student.id)
        .group_by(Student.id)
        .order_by(func.count(ActivityParticipation.id).desc())
        .all()
    )
    return [ActivityItem(student_no=no, name=name, class_name=klass, count=count) for no, name, klass, count in rows]


@router.get("/activity-detail", response_model=list[ActivityDetailItem])
def activity_detail(
    activity_name: str = "",
    activity_date: str = "",
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """按活动/日期查询参与名单，含学号、姓名、情绪。"""
    query = (
        db.query(
            ActivityParticipation.activity_name,
            ActivityParticipation.activity_date,
            Student.student_no,
            Student.name,
            Student.class_name,
            ActivityParticipation.confidence,
            Student.id,
        )
        .join(Student, ActivityParticipation.student_id == Student.id)
    )
    if activity_name:
        query = query.filter(ActivityParticipation.activity_name.contains(activity_name))
    if activity_date:
        query = query.filter(ActivityParticipation.activity_date == activity_date)

    rows = query.order_by(ActivityParticipation.activity_date.desc(), Student.student_no).all()

    # 匹配情绪记录（group_photo 来源）
    emotion_map: dict[int, str] = {}
    for er in db.query(EmotionRecord).filter(EmotionRecord.source == "group_photo").order_by(EmotionRecord.timestamp.desc()).all():
        if er.student_id not in emotion_map:
            emotion_map[er.student_id] = er.emotion_type

    results = []
    for act_name, act_date, student_no, s_name, class_name, confidence, sid in rows:
        results.append(
            ActivityDetailItem(
                activity_name=act_name,
                activity_date=str(act_date),
                student_no=student_no,
                name=s_name,
                class_name=class_name,
                confidence=round(confidence or 0, 4),
                emotion=emotion_map.get(sid),
            )
        )
    return results


@router.get("/activity-export")
def activity_export(
    activity_name: str = "",
    activity_date: str = "",
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """导出活动参与名单 Excel。"""
    query = (
        db.query(
            ActivityParticipation.activity_name,
            ActivityParticipation.activity_date,
            Student.student_no,
            Student.name,
            Student.class_name,
            ActivityParticipation.confidence,
            Student.id,
        )
        .join(Student, ActivityParticipation.student_id == Student.id)
    )
    if activity_name:
        query = query.filter(ActivityParticipation.activity_name.contains(activity_name))
    if activity_date:
        query = query.filter(ActivityParticipation.activity_date == activity_date)

    rows = query.order_by(ActivityParticipation.activity_date.desc(), Student.student_no).all()

    # 匹配情绪
    emotion_map: dict[int, str] = {}
    for er in db.query(EmotionRecord).filter(EmotionRecord.source == "group_photo").order_by(EmotionRecord.timestamp.desc()).all():
        if er.student_id not in emotion_map:
            emotion_map[er.student_id] = er.emotion_type

    # 统计每人累计参与活动次数（按不重复活动名）
    student_ids = {sid for *_, sid in rows}
    activity_counts: dict[int, int] = {}
    if student_ids:
        count_rows = (
            db.query(
                ActivityParticipation.student_id,
                func.count(func.distinct(ActivityParticipation.activity_name)),
            )
            .filter(ActivityParticipation.student_id.in_(student_ids))
            .group_by(ActivityParticipation.student_id)
            .all()
        )
        activity_counts = {sid: cnt for sid, cnt in count_rows}

    records = []
    for act_name, act_date, student_no, s_name, class_name, confidence, sid in rows:
        records.append({
            "activity_name": act_name,
            "activity_date": str(act_date),
            "student_no": student_no,
            "name": s_name,
            "class_name": class_name,
            "confidence": round(confidence or 0, 4),
            "emotion": emotion_map.get(sid, ""),
            "participation_count": activity_counts.get(sid, 0),
        })

    if not records:
        raise HTTPException(status_code=404, detail="没有找到匹配的活动记录")

    safe_name = quote(activity_name or "活动", safe="")
    filename = f"activity-{safe_name}-{datetime.now().strftime('%Y%m%d%H%M%S')}.xlsx"
    stream = build_activity_workbook(records)
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return StreamingResponse(
        stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers,
    )
