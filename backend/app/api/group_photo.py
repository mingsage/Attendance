from datetime import date, datetime
from zoneinfo import ZoneInfo

import numpy as np
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_teacher
from app.core.database import get_db
from app.models import ActivityParticipation, EmotionRecord, Student
from app.services.emotion_service import emotion_service
from app.services.face_service import decode_array, face_service
from app.services.image_utils import read_image


router = APIRouter(prefix="/group-photo", tags=["合照识别"])


@router.post("/recognize", dependencies=[Depends(require_teacher)])
async def group_recognize(
    activity_name: str = Query("班级活动"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    image = await read_image(file)

    # 加载人脸底库
    students_db = db.scalars(
        select(Student).where(Student.face_encoding.isnot(None))
    ).all()
    if not students_db:
        raise HTTPException(status_code=400, detail="底库为空，请先录入学生")

    known_encos = [decode_array(s.face_encoding) for s in students_db]

    # 检测人脸
    faces = face_service.detect_faces(image)
    if not faces:
        raise HTTPException(status_code=400, detail="合照中未检测到人脸")

    recognized = []
    seen_student_ids: set[int] = set()

    for box in faces:
        feature = face_service.extract_feature_by_box(image, box)
        if feature is None:
            continue

        # 计算与所有底库的余弦相似度
        scores = np.array([float(np.dot(feature, enc)) for enc in known_encos])
        if np.any(np.isnan(scores)):
            continue
        best_idx = int(np.argmax(scores))
        best_cos = float(scores[best_idx])
        best_score = (best_cos + 1.0) / 2.0  # 映射到 [0, 1]

        if best_score < 0.55:
            continue

        s = students_db[best_idx]
        if s.id in seen_student_ids:
            continue
        seen_student_ids.add(s.id)

        # 情绪分析
        emotion, emotion_confidence = emotion_service.analyze(image, box)

        now = datetime.now(ZoneInfo("Asia/Shanghai"))
        db.add(
            ActivityParticipation(
                student_id=s.id,
                activity_name=activity_name,
                activity_date=date.today(),
                recognized=True,
                confidence=round(best_score, 4),
            )
        )
        db.add(
            EmotionRecord(
                student_id=s.id,
                timestamp=now,
                emotion_type=emotion,
                confidence=emotion_confidence,
                source="group_photo",
            )
        )

        recognized.append(
            {
                "student_id": s.id,
                "student_no": s.student_no,
                "name": s.name,
                "class_name": s.class_name,
                "emotion": emotion,
                "confidence": round(best_score, 4),
            }
        )

    db.commit()

    return {
        "status": "success",
        "activity_name": activity_name,
        "faces_detected": len(faces),
        "recognized_count": len(recognized),
        "recognized": recognized,
    }
