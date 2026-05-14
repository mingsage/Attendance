from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_teacher
from app.core.database import get_db
from app.models.group import Group
from app.models.student import Student
from app.models.user import User
from app.schemas.group import AddMembersRequest, GroupCreate, GroupDetailOut, GroupOut, GroupUpdate

router = APIRouter(prefix="/groups", tags=["群组"])


def _to_out(group, members_count=0):
    return GroupOut(id=group.id, name=group.name, member_count=members_count)


def _to_detail(group):
    return GroupDetailOut(
        id=group.id,
        name=group.name,
        member_count=len(group.students),
        students=[_student_out(s) for s in group.students],
    )


def _student_out(s):
    return {
        "id": s.id,
        "student_no": s.student_no,
        "name": s.name,
        "class_name": s.class_name,
        "gender": s.gender,
        "grade": s.grade,
        "major": s.major,
        "has_face": s.face_encoding is not None,
        "face_sample_count": s.face_sample_count or 0,
        "face_image_path": s.face_image_path,
        "face_image_url": None,
        "face_status": s.face_status,
    }


@router.get("", response_model=list[GroupOut])
def list_groups(
    db: Session = Depends(get_db),
    user: User = Depends(require_teacher),
):
    groups = db.query(Group).filter(Group.teacher_id == user.id).all()
    return [_to_out(g, len(g.students)) for g in groups]


@router.post("", response_model=GroupOut)
def create_group(
    payload: GroupCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_teacher),
):
    group = Group(name=payload.name, teacher_id=user.id)
    db.add(group)
    db.commit()
    db.refresh(group)
    return _to_out(group, 0)


@router.put("/{group_id}", response_model=GroupOut)
def update_group(
    group_id: int,
    payload: GroupUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_teacher),
):
    group = db.query(Group).filter(Group.id == group_id, Group.teacher_id == user.id).first()
    if not group:
        raise HTTPException(status_code=404, detail="群组不存在")
    if payload.name is not None:
        group.name = payload.name
    db.commit()
    db.refresh(group)
    return _to_out(group, len(group.students))


@router.delete("/{group_id}")
def delete_group(
    group_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_teacher),
):
    group = db.query(Group).filter(Group.id == group_id, Group.teacher_id == user.id).first()
    if not group:
        raise HTTPException(status_code=404, detail="群组不存在")
    group.students.clear()
    db.delete(group)
    db.commit()
    return {"ok": True}


@router.get("/{group_id}", response_model=GroupDetailOut)
def get_group(
    group_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_teacher),
):
    group = db.query(Group).filter(Group.id == group_id, Group.teacher_id == user.id).first()
    if not group:
        raise HTTPException(status_code=404, detail="群组不存在")
    return _to_detail(group)


@router.post("/{group_id}/members", response_model=GroupDetailOut)
def add_members(
    group_id: int,
    payload: AddMembersRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_teacher),
):
    group = db.query(Group).filter(Group.id == group_id, Group.teacher_id == user.id).first()
    if not group:
        raise HTTPException(status_code=404, detail="群组不存在")
    students = db.query(Student).filter(Student.id.in_(payload.student_ids)).all()
    for s in students:
        if s not in group.students:
            group.students.append(s)
    db.commit()
    db.refresh(group)
    return _to_detail(group)


@router.delete("/{group_id}/members/{student_id}")
def remove_member(
    group_id: int,
    student_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_teacher),
):
    group = db.query(Group).filter(Group.id == group_id, Group.teacher_id == user.id).first()
    if not group:
        raise HTTPException(status_code=404, detail="群组不存在")
    student = db.get(Student, student_id)
    if student and student in group.students:
        group.students.remove(student)
        db.commit()
    return {"ok": True}
