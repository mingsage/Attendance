from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import cv2
import numpy as np
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import require_teacher
from app.core.config import get_settings
from app.core.database import get_db
from app.models.activity import ActivityParticipation
from app.models.attendance import AttendanceRecord
from app.models.emotion import EmotionRecord
from app.models.student import Student
from app.services.emotion_service import emotion_service
from app.services.face_service import decode_array, face_service
from app.services.image_utils import read_image, save_upload


router = APIRouter(prefix="/group-photo", tags=["合照识别"])


def _draw_annotations(image, faces_data):
    """在图片上绘制人脸框和编号。"""
    annotated = image.copy()
    colors = [(16, 185, 129), (37, 99, 235), (245, 158, 11), (239, 68, 68)]
    for i, fd in enumerate(faces_data):
        x, y, w, h = fd["bbox"]
        color = colors[i % len(colors)]
        cv2.rectangle(annotated, (x, y), (x + w, y + h), color, 2)
        label = str(fd["no"])
        cv2.putText(annotated, label, (x, y - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
    return annotated


@router.post("/recognize")
async def recognize_group_photo(
    activity_name: str = Query("班级活动"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _=Depends(require_teacher),
):
    image = await read_image(file, max_size=1000 * 1024 * 1024)
    await file.seek(0)
    saved_path = await save_upload(file, get_settings().upload_dir)
    faces = face_service.detect_faces(image)
    if not faces:
        raise HTTPException(status_code=400, detail="合照中未检测到人脸")

    candidates = [
        (student.id, decode_array(student.face_encoding))
        for student in db.query(Student).filter(Student.face_encoding.isnot(None)).all()
    ]
    seen_ids: set[int] = set()
    recognized = []
    faces_data = []
    no = 0

    for box in faces:
        no += 1
        feature = face_service.extract_feature(image, box)
        matched_id, confidence = face_service.compare(feature, candidates)

        student_info = None
        emotion = None
        if matched_id and matched_id not in seen_ids:
            seen_ids.add(matched_id)
            student = db.get(Student, matched_id)
            if student:
                emotion, _ = emotion_service.analyze(image, box)
                student_info = {
                    "id": student.id, "student_no": student.student_no,
                    "name": student.name, "class_name": student.class_name,
                }
                recognized.append({
                    "no": no, "student": student_info, "confidence": round(confidence, 3),
                    "emotion": emotion, "matched": True,
                })
        if not (matched_id and matched_id in seen_ids):
            recognized.append({
                "no": no, "student": None, "confidence": round(confidence, 3),
                "emotion": None, "matched": False,
            })

        faces_data.append({"no": no, "bbox": list(box)})

    # 生成标注图
    annotated_img = _draw_annotations(image, faces_data)
    annot_path = Path(saved_path).with_stem(Path(saved_path).stem + "_annotated")
    cv2.imwrite(str(annot_path), annotated_img)

    return {
        "annotated_image": str(annot_path),
        "face_count": len(faces),
        "recognized": recognized,
        "unmatched_count": len(faces) - len(seen_ids),
    }


@router.post("/save")
def save_group_photo_records(
    payload: dict,       # { session_id, records: [{no, student_id, confidence, emotion}] }
    db: Session = Depends(get_db),
    _=Depends(require_teacher),
):
    session_id = payload.get("session_id")
    records = payload.get("records", [])
    now = datetime.now(ZoneInfo("Asia/Shanghai"))
    saved = 0
    for r in records:
        sid = r.get("student_id")
        if not sid:
            continue
        db.add(AttendanceRecord(
            student_id=sid, session_id=session_id,
            timestamp=now, status="success",
            confidence=r.get("confidence") or 0,
            source="group_photo",
            course_name="", message="合照识别",
        ))
        if r.get("emotion"):
            db.add(EmotionRecord(
                student_id=sid, emotion_type=r["emotion"],
                confidence=0.5, source="group_photo", timestamp=now,
            ))
        db.add(ActivityParticipation(
            student_id=sid, activity_name="合照活动",
            activity_date=now.date(), recognized=True,
            confidence=r.get("confidence") or 0,
        ))
        saved += 1
    db.commit()
    return {"saved_count": saved}
