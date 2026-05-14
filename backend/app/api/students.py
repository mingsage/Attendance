import re
from pathlib import Path

import cv2
import numpy as np
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_teacher
from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import hash_password
from app.models import (
    ActivityParticipation,
    AttendanceRecord,
    EmotionRecord,
    Student,
    User,
)
from app.schemas.student import (
    StudentBatchDeleteRequest,
    StudentBatchDeleteResponse,
    StudentCreate,
    StudentOut,
    StudentUpdate,
)
from app.services.face_service import decode_array, encode_array, face_service
from app.services.image_utils import read_image

router = APIRouter(prefix="/students", tags=["学生管理"])

FACE_NOT_FOUND = "未检测到清晰人脸，请使用正脸、光线充足、无遮挡的照片"
DEFAULT_STUDENT_PASSWORD = "123456"


def parse_face_filename(
    filename: str,
) -> tuple[str, str | None, str | None, str | None]:
    """解析照片文件名：学号-姓名-班级-性别.jpg。"""

    stem = Path(filename or "").stem.strip()
    parts = [item.strip() for item in re.split(r"[-_－—]", stem) if item.strip()]
    student_no = parts[0] if parts else ""
    name = parts[1] if len(parts) >= 2 else None
    class_name = parts[2] if len(parts) >= 3 else None
    gender = parts[3] if len(parts) >= 4 else None
    return student_no, name, class_name, gender


def to_out(student: Student) -> StudentOut:
    raw_path = student.face_image_path
    face_image_url = None
    if raw_path:
        filename = Path(raw_path).name
        face_image_url = f"/face_db/{filename}"
    return StudentOut(
        id=student.id,
        student_no=student.student_no,
        name=student.name,
        class_name=student.class_name,
        gender=student.gender,
        has_face=student.face_encoding is not None,
        face_sample_count=student.face_sample_count
        or (1 if student.face_encoding else 0),
        face_image_path=raw_path,
        face_image_url=face_image_url,
    )


def _ensure_student_user(
    student: Student, db: Session, reset_password: bool = False
) -> User:
    """确保学生有对应的登录账号（username=学号，默认密码=123456）。"""
    existing = db.query(User).filter(User.student_id == student.id).first()
    username_user = db.query(User).filter(User.username == student.student_no).first()
    if existing:
        if username_user and username_user.id != existing.id:
            raise HTTPException(status_code=400, detail="学号对应的登录账号已存在")
        existing.username = student.student_no
        existing.role = "student"
        if reset_password:
            existing.password_hash = hash_password(DEFAULT_STUDENT_PASSWORD)
        return existing
    if username_user:
        if username_user.role != "student":
            raise HTTPException(status_code=400, detail="学号对应的登录账号已被其他角色使用")
        if username_user.student_id and username_user.student_id != student.id:
            raise HTTPException(status_code=400, detail="学号对应的登录账号已绑定其他学生")
        username_user.role = "student"
        username_user.student_id = student.id
        if reset_password:
            username_user.password_hash = hash_password(DEFAULT_STUDENT_PASSWORD)
        return username_user
    user = User(
        username=student.student_no,
        password_hash=hash_password(DEFAULT_STUDENT_PASSWORD),
        role="student",
        student_id=student.id,
    )
    db.add(user)
    return user


def merge_face_feature(student: Student, feature: np.ndarray) -> None:
    """把同一学生的多张人脸照片合并成一个平均特征。"""

    old_count = int(student.face_sample_count or 0)
    if student.face_encoding and old_count > 0:
        old_feature = decode_array(student.face_encoding)
        if old_feature.shape == feature.shape:
            merged = old_feature * old_count + feature
            merged /= old_count + 1
            merged /= np.linalg.norm(merged) or 1.0
            student.face_encoding = encode_array(merged)
            student.face_sample_count = old_count + 1
            return

    student.face_encoding = encode_array(feature)
    student.face_sample_count = 1


def save_face_image(student: Student, image: np.ndarray, filename: str | None) -> str:
    settings = get_settings()
    suffix = Path(filename or "face.jpg").suffix.lower() or ".jpg"
    next_index = int(student.face_sample_count or 0) + 1
    path = settings.face_db_dir / f"{student.student_no}_{next_index}{suffix}"
    cv2.imwrite(str(path), image)
    return str(path)


def resolve_backend_root() -> Path:
    return Path(__file__).resolve().parents[2]


def resolve_face_dir(backend_root: Path) -> Path:
    settings = get_settings()
    face_dir = settings.face_db_dir
    if not face_dir.is_absolute():
        face_dir = backend_root / face_dir
    return face_dir


def delete_face_files(student: Student, face_dir: Path, backend_root: Path) -> int:
    deleted = 0
    if student.student_no and face_dir.exists():
        for path in face_dir.glob(f"{student.student_no}_*"):
            try:
                path.unlink()
                deleted += 1
            except FileNotFoundError:
                pass
    if student.face_image_path:
        path = Path(student.face_image_path)
        if not path.is_absolute():
            path = backend_root / path
        try:
            path.unlink()
            deleted += 1
        except FileNotFoundError:
            pass
    return deleted


@router.get("", response_model=list[StudentOut])
def list_students(keyword: str = "", db: Session = Depends(get_db)):
    query = db.query(Student)
    if keyword:
        query = query.filter(
            (Student.name.contains(keyword)) | (Student.student_no.contains(keyword))
        )
    return [to_out(item) for item in query.order_by(Student.id.desc()).all()]


@router.get("/by-no/{student_no}", response_model=StudentOut)
def get_student_by_no(student_no: str, db: Session = Depends(get_db)):
    student = db.query(Student).filter(Student.student_no == student_no).first()
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")
    return to_out(student)


@router.get("/me", response_model=StudentOut)
def get_my_info(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """获取当前学生自己的信息。"""
    if not user.student_id:
        raise HTTPException(status_code=400, detail="当前账号未绑定学生信息")
    student = db.get(Student, user.student_id)
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")
    return to_out(student)


@router.get("/{student_id}", response_model=StudentOut)
def get_student(student_id: int, db: Session = Depends(get_db)):
    student = db.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")
    return to_out(student)


@router.post("", response_model=StudentOut, dependencies=[Depends(require_teacher)])
def create_student(payload: StudentCreate, db: Session = Depends(get_db)):
    if db.query(Student).filter(Student.student_no == payload.student_no).first():
        raise HTTPException(status_code=400, detail="学号已存在")
    student = Student(**payload.model_dump())
    db.add(student)
    db.flush()
    _ensure_student_user(student, db)
    db.commit()
    db.refresh(student)
    return to_out(student)


@router.put(
    "/{student_id}", response_model=StudentOut, dependencies=[Depends(require_teacher)]
)
def update_student(
    student_id: int, payload: StudentUpdate, db: Session = Depends(get_db)
):
    student = db.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")
    updates = payload.model_dump(exclude_unset=True)
    new_student_no = updates.get("student_no")
    if new_student_no and new_student_no != student.student_no:
        duplicate = (
            db.query(Student)
            .filter(Student.student_no == new_student_no, Student.id != student.id)
            .first()
        )
        if duplicate:
            raise HTTPException(status_code=400, detail="学号已存在")
    for key, value in updates.items():
        setattr(student, key, value)
    _ensure_student_user(student, db)
    db.commit()
    db.refresh(student)
    return to_out(student)


@router.post(
    "/{student_id}/reset-password",
    dependencies=[Depends(require_teacher)],
)
def reset_student_password(student_id: int, db: Session = Depends(get_db)):
    student = db.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")
    user = _ensure_student_user(student, db, reset_password=True)
    db.commit()
    return {
        "ok": True,
        "username": user.username,
        "default_password": DEFAULT_STUDENT_PASSWORD,
    }


@router.delete("/{student_id}", dependencies=[Depends(require_teacher)])
def delete_student(student_id: int, db: Session = Depends(get_db)):
    student = db.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")

    backend_root = resolve_backend_root()
    face_dir = resolve_face_dir(backend_root)

    db.query(AttendanceRecord).filter(
        AttendanceRecord.student_id == student.id
    ).delete(synchronize_session=False)
    db.query(EmotionRecord).filter(EmotionRecord.student_id == student.id).delete(
        synchronize_session=False
    )
    db.query(ActivityParticipation).filter(
        ActivityParticipation.student_id == student.id
    ).delete(synchronize_session=False)
    db.query(User).filter(User.student_id == student.id).delete(
        synchronize_session=False
    )
    delete_face_files(student, face_dir, backend_root)
    db.delete(student)
    db.commit()
    return {"ok": True}


@router.post(
    "/batch-delete",
    response_model=StudentBatchDeleteResponse,
    dependencies=[Depends(require_teacher)],
)
def batch_delete_students(
    payload: StudentBatchDeleteRequest, db: Session = Depends(get_db)
):
    student_ids = list(dict.fromkeys(payload.student_ids))
    if not student_ids:
        raise HTTPException(status_code=400, detail="请至少选择一名学生")

    students = db.query(Student).filter(Student.id.in_(student_ids)).all()
    found_ids = {student.id for student in students}
    missing_ids = [
        student_id for student_id in student_ids if student_id not in found_ids
    ]

    backend_root = resolve_backend_root()
    face_dir = resolve_face_dir(backend_root)
    deleted_images = 0

    for student in students:
        db.query(AttendanceRecord).filter(
            AttendanceRecord.student_id == student.id
        ).delete(synchronize_session=False)
        db.query(EmotionRecord).filter(EmotionRecord.student_id == student.id).delete(
            synchronize_session=False
        )
        db.query(ActivityParticipation).filter(
            ActivityParticipation.student_id == student.id
        ).delete(synchronize_session=False)
        db.query(User).filter(User.student_id == student.id).delete(
            synchronize_session=False
        )
        deleted_images += delete_face_files(student, face_dir, backend_root)
        db.delete(student)

    db.commit()
    return StudentBatchDeleteResponse(
        deleted_count=len(students),
        missing_ids=missing_ids,
        deleted_images=deleted_images,
    )


@router.post(
    "/me/face",
    response_model=StudentOut,
)
async def upload_my_face(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """学生自己上传/拍摄人脸照片。"""
    if not user.student_id:
        raise HTTPException(status_code=400, detail="当前账号未绑定学生信息")
    student = db.get(Student, user.student_id)
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")

    image = await read_image(file)
    feature = face_service.extract_detected_feature(image)
    if feature is None:
        raise HTTPException(status_code=400, detail=FACE_NOT_FOUND)

    student.face_image_path = save_face_image(student, image, file.filename)
    merge_face_feature(student, feature)
    db.commit()
    db.refresh(student)
    return to_out(student)


@router.post(
    "/{student_id}/face",
    response_model=StudentOut,
    dependencies=[Depends(require_teacher)],
)
async def upload_face(
    student_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)
):
    student = db.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")

    image = await read_image(file)
    feature = face_service.extract_detected_feature(image)
    if feature is None:
        raise HTTPException(status_code=400, detail=FACE_NOT_FOUND)

    student.face_image_path = save_face_image(student, image, file.filename)
    merge_face_feature(student, feature)
    db.commit()
    db.refresh(student)
    return to_out(student)


@router.post("/faces/batch", dependencies=[Depends(require_teacher)])
async def batch_upload_faces(
    files: list[UploadFile] = File(...), db: Session = Depends(get_db)
):
    """批量导入人脸库，文件名格式：学号-姓名-班级-性别.jpg。"""

    imported = []
    failed = []

    for file in files:
        student_no, name, class_name, gender = parse_face_filename(file.filename or "")
        if not student_no:
            failed.append({"filename": file.filename, "reason": "文件名缺少学号"})
            continue

        try:
            image = await read_image(file)
            feature = face_service.extract_detected_feature(image)
            if feature is None:
                failed.append({"filename": file.filename, "reason": FACE_NOT_FOUND})
                continue

            student = db.query(Student).filter(Student.student_no == student_no).first()
            if not student:
                if not name or not class_name:
                    failed.append(
                        {
                            "filename": file.filename,
                            "reason": "新学生照片必须使用：学号-姓名-班级-性别.jpg",
                        }
                    )
                    continue
                student = Student(
                    student_no=student_no,
                    name=name,
                    class_name=class_name,
                    gender=gender,
                )
                db.add(student)
                db.flush()
            else:
                if name:
                    student.name = name
                if class_name:
                    student.class_name = class_name
                if gender:
                    student.gender = gender

            _ensure_student_user(student, db)

            student.face_image_path = save_face_image(student, image, file.filename)
            merge_face_feature(student, feature)
            imported.append(
                {
                    "student_no": student.student_no,
                    "name": student.name,
                    "class_name": student.class_name,
                    "gender": student.gender,
                    "face_sample_count": student.face_sample_count,
                    "filename": file.filename,
                }
            )
        except HTTPException as exc:
            failed.append({"filename": file.filename, "reason": exc.detail})
        except Exception as exc:  # noqa: BLE001 - 单张照片失败不应中断整批导入。
            failed.append({"filename": file.filename, "reason": str(exc)})

    db.commit()
    return {
        "imported_count": len(imported),
        "failed_count": len(failed),
        "imported": imported,
        "failed": failed,
    }


@router.post("/faces/rebuild", dependencies=[Depends(require_teacher)])
def rebuild_face_features(db: Session = Depends(get_db)):
    """根据已保存的人脸照片重建特征；只保留当前代表照片的一份特征。"""

    rebuilt = []
    failed = []
    students = db.query(Student).filter(Student.face_image_path.isnot(None)).all()
    for student in students:
        path = Path(student.face_image_path or "")
        if not path.exists():
            failed.append(
                {
                    "student_no": student.student_no,
                    "name": student.name,
                    "reason": "照片文件不存在",
                }
            )
            continue
        image = cv2.imread(str(path))
        if image is None:
            failed.append(
                {
                    "student_no": student.student_no,
                    "name": student.name,
                    "reason": "照片读取失败",
                }
            )
            continue
        feature = face_service.extract_detected_feature(image)
        if feature is None:
            failed.append(
                {
                    "student_no": student.student_no,
                    "name": student.name,
                    "reason": FACE_NOT_FOUND,
                }
            )
            continue
        student.face_encoding = encode_array(feature)
        student.face_sample_count = 1
        rebuilt.append({"student_no": student.student_no, "name": student.name})
    db.commit()
    return {
        "rebuilt_count": len(rebuilt),
        "failed_count": len(failed),
        "rebuilt": rebuilt,
        "failed": failed,
    }
