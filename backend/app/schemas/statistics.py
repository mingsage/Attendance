from pydantic import BaseModel


class CountItem(BaseModel):
    name: str
    value: int


class ActivityItem(BaseModel):
    id: int | None = None
    student_no: str
    name: str
    class_name: str
    count: int
