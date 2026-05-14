from pydantic import BaseModel

from app.schemas.student import StudentOut


class GroupCreate(BaseModel):
    name: str


class GroupUpdate(BaseModel):
    name: str | None = None


class GroupOut(BaseModel):
    id: int
    name: str
    member_count: int = 0

    model_config = {"from_attributes": True}


class GroupDetailOut(GroupOut):
    students: list[StudentOut] = []


class AddMembersRequest(BaseModel):
    student_ids: list[int]
