from fastapi import APIRouter

from app.api import attendance, auth, emotions, group_photo, statistics, students


api_router = APIRouter(prefix="/api")
api_router.include_router(auth.router)
api_router.include_router(students.router)
api_router.include_router(attendance.router)
api_router.include_router(group_photo.router)
api_router.include_router(statistics.router)
api_router.include_router(emotions.router)
