from pydantic import BaseModel, Field


class StudentCreate(BaseModel):
    student_no: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=64)
    class_name: str = Field(min_length=1, max_length=64)
    gender: str | None = Field(default=None, max_length=16)


class StudentUpdate(BaseModel):
    student_no: str | None = None
    name: str | None = None
    class_name: str | None = None
    gender: str | None = None


class StudentOut(BaseModel):
    id: int
    student_no: str
    name: str
    class_name: str
    gender: str | None = None
    has_face: bool
    face_sample_count: int = 0
    face_image_path: str | None = None
    face_image_url: str | None = None

    class Config:
        from_attributes = True


class StudentBatchDeleteRequest(BaseModel):
    student_ids: list[int] = Field(default_factory=list)


class StudentBatchDeleteResponse(BaseModel):
    deleted_count: int
    missing_ids: list[int] = Field(default_factory=list)
    deleted_images: int = 0
