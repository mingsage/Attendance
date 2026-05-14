from fastapi import APIRouter

from app.api import (
    attendance,
    auth,
    courses,
    emotions,
    group_photo,
    groups,
    statistics,
    students,
    supplements,
)


api_router = APIRouter(prefix="/api")
api_router.include_router(auth.router)
api_router.include_router(students.router)
api_router.include_router(attendance.router)
api_router.include_router(courses.router)
api_router.include_router(courses.session_router)
api_router.include_router(group_photo.router)
api_router.include_router(groups.router)
api_router.include_router(statistics.router)
api_router.include_router(emotions.router)
api_router.include_router(supplements.router)
