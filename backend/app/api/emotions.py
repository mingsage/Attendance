from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.attendance import AttendanceRecord
from app.models.emotion import EmotionRecord
from app.models.student import Student
from app.models.user import User


router = APIRouter(prefix="/emotions", tags=["情绪记录"])


@router.delete("/records")
def delete_all_emotions(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """一键删除所有情绪记录。"""
    if user.role not in ("admin", "teacher"):
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="仅管理员和教师可删除情绪记录")
    count = db.query(EmotionRecord).delete()
    db.commit()
    return {"deleted": count, "message": f"已删除 {count} 条情绪记录"}


@router.get("/records")
def emotion_records(
    keyword: str = "",
    source: str = "",
    limit: int = 200,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """查询情绪明细，满足 PPT 对学号、姓名、时间、情绪类型完整记录的要求。"""

    query = db.query(EmotionRecord).options(joinedload(EmotionRecord.student))
    if user.role == "student":
        if not user.student_id:
            return []
        query = query.filter(
            EmotionRecord.student_id == user.student_id,
            EmotionRecord.source == "attendance",
        )
    if source:
        query = query.filter(EmotionRecord.source == source)
    if keyword:
        query = query.join(Student, isouter=True).filter((Student.name.contains(keyword)) | (Student.student_no.contains(keyword)))
    rows = query.order_by(EmotionRecord.timestamp.desc()).limit(limit).all()
    return [
        {
            "id": row.id,
            "timestamp": row.timestamp,
            "student_id": row.student.id if row.student else None,
            "student_no": row.student.student_no if row.student else "",
            "name": row.student.name if row.student else "",
            "class_name": row.student.class_name if row.student else "",
            "emotion_type": row.emotion_type,
            "confidence": row.confidence,
            "source": row.source,
            "photo_url": _lookup_photo_url(db, row),
        }
        for row in rows
    ]


def _lookup_photo_url(db: Session, emotion_record: EmotionRecord) -> str | None:
    """查找关联的考勤签到照片。"""
    if emotion_record.source != "attendance" or not emotion_record.student_id:
        return None
    att = (
        db.query(AttendanceRecord)
        .filter(
            AttendanceRecord.student_id == emotion_record.student_id,
            AttendanceRecord.timestamp == emotion_record.timestamp,
            AttendanceRecord.photo_path.isnot(None),
        )
        .first()
    )
    if att and att.photo_path:
        return f"/uploads/{att.photo_path}"
    return None
