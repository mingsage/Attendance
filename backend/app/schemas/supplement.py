from datetime import datetime

from pydantic import BaseModel


class SupplementCreate(BaseModel):
    session_id: int
    reason: str = ""


class SupplementOut(BaseModel):
    id: int
    student_id: int
    student_name: str = ""
    student_no: str = ""
    session_id: int
    session_info: str = ""
    reason: str
    status: str
    created_at: datetime | None = None

    model_config = {"from_attributes": True}
