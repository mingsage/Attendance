from datetime import datetime
from zoneinfo import ZoneInfo

import cv2
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import require_teacher
from app.core.config import get_settings
from app.core.database import get_db
from app.models.attendance import AttendanceRecord
from app.models.emotion import EmotionRecord
from app.models.student import Student
from app.services.emotion_service import emotion_service
from app.services.face_service import decode_array, face_service
from app.services.image_utils import read_image, save_upload


router = APIRouter(prefix="/group-photo", tags=["合照识别"])


@router.post("/recognize", dependencies=[Depends(require_teacher)])
async def recognize_group_photo(
    activity_name: str = Query("班级活动"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    image = await read_image(file)
    await file.seek(0)
    saved_path = await save_upload(file, get_settings().upload_dir)

    # 保存合照作为考勤照片
    photo_dir = get_settings().upload_dir / "group_photos"
    photo_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(ZoneInfo("Asia/Shanghai"))
    group_photo_path = f"group_photos/{ts.strftime('%Y%m%d%H%M%S')}.jpg"
    cv2.imwrite(str(get_settings().upload_dir / group_photo_path), image)

    faces = face_service.detect_faces(image)
    if not faces:
        raise HTTPException(status_code=400, detail="合照中未检测到人脸")

    candidates = [
        (student.id, decode_array(student.face_encoding))
        for student in db.query(Student).filter(Student.face_encoding.isnot(None)).all()
    ]
    results = []
    seen_student_ids: set[int] = set()
    now = datetime.now(ZoneInfo("Asia/Shanghai"))
    for box in faces:
        feature = face_service.extract_feature(image, box)
        matched_id, confidence = face_service.compare(feature, candidates)
        if not matched_id or matched_id in seen_student_ids:
            continue
        student = db.get(Student, matched_id)
        if not student:
            continue
        seen_student_ids.add(matched_id)
        emotion, emotion_confidence = emotion_service.analyze(image, box)
        db.add(
            AttendanceRecord(
                student_id=matched_id,
                timestamp=now,
                status="success",
                confidence=round(confidence, 3),
                liveness_score=0,
                emotion_type=emotion,
                course_name=activity_name,
                message=f"合照识别：{activity_name}",
                photo_path=group_photo_path,
            )
        )
        db.add(
            EmotionRecord(
                student_id=matched_id,
                emotion_type=emotion,
                confidence=emotion_confidence,
                source="group_photo",
                timestamp=now,
            )
        )
        results.append(
            {
                "student_id": student.id,
                "student_no": student.student_no,
                "name": student.name,
                "class_name": student.class_name,
                "confidence": round(confidence, 3),
                "emotion": emotion,
            }
        )
    db.commit()
    return {"image_path": saved_path, "face_count": len(faces), "recognized_count": len(results), "results": results}
