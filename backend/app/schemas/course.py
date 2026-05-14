from datetime import date, datetime

from pydantic import BaseModel


class CourseCreate(BaseModel):
    name: str
    semester: str
    school_year: str


class CourseUpdate(BaseModel):
    name: str | None = None
    semester: str | None = None
    school_year: str | None = None


class CourseOut(BaseModel):
    id: int
    name: str
    semester: str
    school_year: str

    model_config = {"from_attributes": True}


class SessionCreate(BaseModel):
    course_id: int
    date: date
    session_no: str
    type: str = "camera"  # camera / group_photo / manual
    group_id: int


class SessionOut(BaseModel):
    id: int
    course_id: int
    course_name: str = ""
    date: str
    session_no: str
    type: str
    group_id: int
    group_name: str = ""
    created_at: datetime | None = None

    model_config = {"from_attributes": True}
