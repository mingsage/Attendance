# 班级考勤系统

基于 **FastAPI + Vue 3** 的智能人脸识别考勤管理平台，支持单人或合照批量签到、活体检测、情绪分析、课程统计与 Excel 导出。

## 功能

- **人脸签到** — 上传照片自动检测人脸、提取特征、比对数据库完成签到
- **活体检测** — 签到时可开启活体检测（眨眼、转头、张嘴），防止照片/视频伪造
- **合照识别** — 上传班级合照，一键识别所有已录入人脸的学生并批量生成考勤记录
- **情绪分析** — 签到同时检测七类情绪（happy、sad、angry 等）并记录
- **学生管理** — 学生信息的增删改查，支持单张或批量（文件名解析）导入人脸照片
- **人脸库重建** — 在已保存照片基础上批量重建人脸特征向量
- **课程考勤统计** — 按课程和日期的出勤统计，支持导出 Excel
- **情绪统计** — 全局情绪分布概览
- **活动参与统计** — 活动识别记录汇总
- **数据导出** — 考勤记录和统计报表一键导出为 xlsx

## 技术栈

| 层 | 技术 |
| --- | --- |
| 后端框架 | FastAPI + SQLAlchemy + Pydantic |
| 数据库 | SQLite（可切换） |
| 人脸识别 | OpenCV + face_recognition |
| 活体检测 | OpenCV 动作分析 |
| 情绪识别 | 基于面部特征分类 |
| 前端框架 | Vue 3 + Vite |
| UI 组件 | Element Plus |
| 状态管理 | Pinia |
| 图表 | ECharts |
| HTTP 客户端 | Axios |

## 快速启动

### 后端

```bash
cd backend

# 安装依赖
pip install -r requirements.txt

# 启动服务（监听 8000 端口）
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

首次启动会自动创建 SQLite 数据库文件和默认教师账号。

### 前端

```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

默认在 `http://127.0.0.1:5173` 启动。

### 默认登录账号

| 角色 | 用户名 | 密码 |
| --- | --- | --- |
| 教师 | `teacher` | `123456` |

## 项目结构

```
backend/
├── app/
│   ├── api/           # 路由层：auth / students / attendance / emotions / statistics / group_photo
│   ├── core/          # 配置、数据库引擎、安全工具
│   ├── models/        # SQLAlchemy ORM 模型
│   ├── schemas/       # Pydantic 请求/响应模型
│   └── services/      # 业务服务：人脸识别、活体检测、情绪分析、导出、图片工具
├── database/          # SQLite 数据文件和人脸照片（自动生成）
└── uploads/           # 上传文件存放（自动生成）

frontend/
├── src/
│   ├── components/    # 公共组件
│   ├── layout/        # 整体布局
│   ├── views/         # 页面：Login / Dashboard / Attendance / Students / Records / EmotionStats / ActivityStats / GroupPhoto
│   └── stores/        # Pinia 状态管理
└── package.json
```
