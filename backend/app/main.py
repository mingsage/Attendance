from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import api_router
from app.core.config import get_settings
from app.core.database import Base, engine
from app.core.security import hash_password
from app.models import User


def create_app() -> FastAPI:
    settings = get_settings()
    Base.metadata.create_all(bind=engine)
    ensure_schema()

    app = FastAPI(title=settings.app_name)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router)
    app.mount("/uploads", StaticFiles(directory=settings.upload_dir), name="uploads")
    app.mount("/face_db", StaticFiles(directory=settings.face_db_dir), name="face_db")

    @app.get("/")
    def health():
        return {"status": "ok", "service": settings.app_name}

    return app


def ensure_schema() -> None:
    """轻量迁移：SQLite 数据库缺失列时自动补上。"""

    if engine.dialect.name != "sqlite":
        return
    with engine.begin() as conn:
        columns = [row[1] for row in conn.exec_driver_sql("PRAGMA table_info(students)").fetchall()]
        if "gender" not in columns:
            conn.exec_driver_sql("ALTER TABLE students ADD COLUMN gender VARCHAR(16)")
        if "face_sample_count" not in columns:
            conn.exec_driver_sql("ALTER TABLE students ADD COLUMN face_sample_count INTEGER DEFAULT 0")

        ar_columns = [row[1] for row in conn.exec_driver_sql("PRAGMA table_info(attendance_records)").fetchall()]
        if "photo_path" not in ar_columns:
            conn.exec_driver_sql("ALTER TABLE attendance_records ADD COLUMN photo_path VARCHAR(512)")


app = create_app()


def seed_admin() -> None:
    """创建默认教师账号，方便首次启动后直接进入系统。"""

    from app.core.database import SessionLocal

    db = SessionLocal()
    try:
        if not db.query(User).filter(User.username == "teacher").first():
            db.add(User(username="teacher", password_hash=hash_password("123456"), role="teacher"))
            db.commit()
    finally:
        db.close()


seed_admin()
