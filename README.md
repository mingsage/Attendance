# 班级考勤系统

基于 **FastAPI + Vue 3** 的智能人脸识别考勤管理平台，支持单人或合照批量签到、11 维活体检测、情绪分析、课程统计与 Excel 导出。

## 功能

- **人脸签到** — 拍照/上传，自动检测人脸、提取 ArcFace 512d 特征、比对数据库完成签到
- **活体检测** — 11 维综合评分：rPPG 脉搏波 + 摩尔纹检测 + 光流时序 + DeepFace MiniFASNet + 动态阈值
- **动作挑战** — 随机动作（微笑/转头/张嘴），InsightFace 5 关键点精确验证
- **合照识别** — 上传班级合照，SCRFD 检测 + ArcFace 批量识别 + 自动写入活动参与记录
- **情绪分析** — HSEmotion (EfficientNet-B0) + DeepFace + OpenCV 三引擎混合，7 类情绪分类
- **学生管理** — 增删改查，单张/批量（文件名解析）导入人脸，512d 特征加权合并
- **课程考勤统计** — 按课程和日期的出勤统计，应到/实到/缺勤/到课率，支持 Excel 导出
- **情绪统计** — ECharts 饼图 + 明细记录表
- **活动参与统计** — 合照识别自动记录活动次数

## 技术栈

| 层 | 技术 |
| --- | --- |
| 后端框架 | FastAPI + SQLAlchemy 2.x + Pydantic v2 |
| 数据库 | SQLite（可切换 PostgreSQL） |
| 人脸检测 | InsightFace SCRFD-10GF |
| 人脸识别 | InsightFace ArcFace ResNet50 (512d) |
| 活体检测 | 11 维：rPPG + 摩尔纹 + 光流 + DeepFace + 传统 CV |
| 情绪识别 | HSEmotion EfficientNet-B0 + DeepFace + OpenCV 三引擎 |
| 前端框架 | Vue 3 + Vite |
| UI 组件 | Element Plus |
| 图表 | ECharts |
| HTTP | Axios |

## 环境要求

| 依赖 | 说明 |
| --- | --- |
| Python 3.9+ | 后端运行环境 |
| Node.js 18+ | 前端构建 |
| 摄像头 | 浏览器需授权摄像头访问 |
| 磁盘空间 | ~2GB（含 InsightFace buffalo_l 326MB + DeepFace 模型 + PyTorch） |

## 快速启动

### 1. 后端

```bash
cd backend

# 安装依赖（含 InsightFace / DeepFace / HSEmotion / PyTorch）
pip install -r requirements.txt

# 启动服务
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

> **注意**：首次启动时 InsightFace 会自动下载 buffalo_l 模型包（~326MB）到 `~/.insightface/`，HSEmotion 会自动下载 `enet_b0_8_best_afew.pt`（~20MB）到 `~/.hsemotion/`。需保证网络通畅。

### 2. 前端

```bash
cd frontend
npm install
npm run dev
# → http://127.0.0.1:5173
```

### 3. 初始化

1. 浏览器打开 `http://127.0.0.1:5173`
2. 用教师账号登录：`teacher` / `123456`
3. 进入「学生管理」→「批量导入人脸」批量录入学生照片
4. 或进入「学生管理」→「新增学生」→「录入人脸」逐个录入
5. 切换「考勤识别」页面，开启摄像头即可签到

### 4. 人脸特征重建（首次升级必须）

如果数据库中已有学生（128d 旧特征），需要运行重建接口升级到 512d：

```bash
curl -X POST http://localhost:8000/api/students/faces/rebuild \
  -H "Authorization: Bearer <token>"
```

### 默认账号

| 角色 | 用户名 | 密码 |
| --- | --- | --- |
| 教师 | `teacher` | `123456` |

## 项目结构

```
backend/
├── app/
│   ├── api/              # 路由层
│   │   ├── __init__.py   # 路由聚合
│   │   ├── auth.py       # 登录/注册
│   │   ├── attendance.py # 签到/活体挑战/记录/导出
│   │   ├── students.py   # 学生CRUD/人脸批量导入/重建
│   │   ├── group_photo.py# 合照识别
│   │   ├── emotions.py   # 情绪记录查询
│   │   ├── statistics.py # 仪表盘/考勤统计/活动统计
│   │   └── deps.py       # JWT认证/权限依赖
│   ├── services/         # 业务逻辑
│   │   ├── face_service.py      # InsightFace SCRFD+ArcFace
│   │   ├── liveness_service.py  # 11维活体检测
│   │   ├── emotion_service.py   # 三引擎情绪分析
│   │   ├── export_service.py    # Excel导出
│   │   └── image_utils.py       # 图片读取/保存
│   ├── models/           # SQLAlchemy ORM (5表)
│   ├── schemas/          # Pydantic 校验
│   └── core/             # 配置/数据库/安全
├── database/             # SQLite DB + 人脸照片
└── uploads/              # 上传文件

frontend/
├── src/
│   ├── views/            # 页面组件 (8个)
│   ├── api/              # Axios封装 (http.js + modules.js)
│   ├── stores/           # Pinia状态 (auth.js)
│   ├── router/           # 路由守卫
│   ├── layout/           # 主布局
│   └── components/       # 公共组件 (StudentDetail)
└── package.json
```

## 相关文档

| 文档 | 说明 |
| --- | --- |
| `docs/课程设计报告.md` | 完整课程设计报告（需求分析+系统设计+代码实现） |
| `docs/架构升级方案.md` | 技术架构设计文档 |
| `docs/第三方库选型分析.md` | DeepFace / InsightFace / HSEmotion 对比分析 |
| `docs/功能实现方案详细分析.md` | 按评分项逐条的优劣分析+整改方案 |
| `docs/request.md` | 评分标准 |
