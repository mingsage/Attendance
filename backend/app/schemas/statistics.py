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


class ActivityDetailItem(BaseModel):
    activity_name: str
    activity_date: str
    student_no: str
    name: str
    class_name: str
    confidence: float
    emotion: str | None = None

    class Config:
        from_attributes = True
