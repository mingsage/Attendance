# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

班级考勤系统 — A face-recognition attendance management platform. Backend is FastAPI + SQLAlchemy (SQLite), frontend is Vue 3 + Vite + Element Plus. Supports individual/group check-in via face recognition, liveness detection, emotion analysis, course statistics, and Excel export.

## Commands

```bash
# Backend (from backend/)
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Frontend (from frontend/)
npm install
npm run dev        # Dev server at http://127.0.0.1:5173
npm run build      # Production build
```

No test or linting scripts are currently configured.

## Architecture

### Backend (`backend/app/`)

```
api/            # FastAPI route handlers (6 modules)
  auth.py         POST /api/auth/login, /register
  students.py     CRUD + face upload/batch import/rebuild features
  attendance.py   Check-in, records list/export, liveness toggle
  group_photo.py  POST /group-photo/recognize (batch check-in from class photo)
  statistics.py   Dashboard, emotion, course, attendance stats + Excel export
  emotions.py     Emotion detail records
  deps.py         Auth dependencies (get_current_user, require_teacher)
core/
  config.py       Settings via pydantic-settings (DB URL, face threshold, etc.)
  database.py     SQLAlchemy engine + session factory (SQLite default)
  security.py     bcrypt password hashing, JWT encode/decode (python-jose)
models/           SQLAlchemy ORM models
  student.py      Student (with face_encoding as LargeBinary blob)
  user.py         User (teacher/student roles, optional FK to Student)
  attendance.py   AttendanceRecord
  emotion.py      EmotionRecord
  activity.py     ActivityParticipation (for group photo activities)
services/
  face_service.py      Face detection (YuNet/SFace ONNX models preferred, Haar/HOG/LBP fallback) + feature extraction + identification
  liveness_service.py  Anti-spoofing via DeepFace MiniFASNet + FFT + LBP + color diversity
  emotion_service.py   Emotion classification (DeepFace preferred, OpenCV heuristic fallback)
  export_service.py    Excel export via openpyxl
  image_utils.py       Upload validation + OpenCV decode
```

- All routes are mounted under `/api` via `api_router` in `api/__init__.py`
- Dependency injection via `Depends(get_db)` for DB sessions, `Depends(get_current_user)` / `Depends(require_teacher)` for auth
- Default teacher account: `teacher` / `123456` (auto-seeded on first startup)
- Face encodings stored as `np.float32` binary blobs in SQLite

### Frontend (`frontend/src/`)

```
api/
  http.js         Axios instance with JWT interceptor + error toast
  modules.js      All API calls organized by domain (auth, student, attendance, etc.)
router/
  index.js        Vue Router with auth guard (redirect to /login if no token)
stores/
  auth.js         Pinia store for token/username/role (persisted to localStorage)
views/            Pages mapped by router
  Login.vue       Login form
  Dashboard.vue   Overview stats
  Attendance.vue  Check-in page with camera/file upload + liveness challenge
  Students.vue    Student CRUD + face import
  Records.vue     Attendance records table + export
  GroupPhoto.vue  Batch check-in via group photo upload
  EmotionStats.vue / ActivityStats.vue  Charts (ECharts)
layout/
  MainLayout.vue  Sidebar + header layout
components/
  StudentDetail.vue  Student detail/edit dialog
```

- JWT token stored in `localStorage` and attached to all requests via Axios interceptor
- Route guard in `router/index.js` checks `auth.isLoggedIn` before each navigation

### Face Recognition Pipeline

1. **Detection**: YuNet ONNX model (via OpenCV DNN) → fallback to Haar Cascade → fallback to center crop
2. **Feature extraction**: SFace ONNX model → fallback to custom HOG+LBP+DCT hybrid feature
3. **Matching**: Cosine similarity → normalized to [0,1]; threshold = 0.58 (configurable via `face_threshold`)

### Key Design Decisions

- **Face encoding merging**: Multiple photos of the same student are merged via running average (weighted by count)
- **Liveness detection**: Soft voting across 7 dimensions (blur, brightness, texture, FFT, LBP, color, DeepFace anti-spoofing); disabled by default via `LIVENESS_ENABLED` flag in `attendance.py`
- **Batch face import**: Filename format `学号-姓名-班级-性别.jpg` — parsing in `parse_face_filename()` supports Chinese dash and underscore separators
- **DB migrations**: No Alembic; schema updates done via `ensure_schema()` in `main.py` using raw SQL `PRAGMA table_info` + `ALTER TABLE`
- **Emotion fallback**: DeepFace → OpenCV heuristic (smile/eye detectors + gradient/contrast analysis)
- **No TypeScript**: Backend uses Pydantic v2, frontend is plain JS
