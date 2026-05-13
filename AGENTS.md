# 活体检测优化方案

## 问题分析

### 问题 1：照片能成功签到

**根因**：后端 `liveness_service.py` 的防欺骗阈值过低（有 DeepFace 时 0.38，无 DeepFace 时仅 0.30），且 DeepFace 不在 `requirements.txt` 中（optional import），大量部署场景下完全依赖传统 CV 方法，检测能力很弱。

**关键代码**：
- `liveness_service.py:190-210` — 综合评分的阈值和权重
- `attendance.py:80` — `liveness_passed = (not LIVENESS_ENABLED) or liveness_score >= 0.30`

### 问题 2：活体动作挑战未强制执行

**根因**：前端 `/liveness-challenge` 接口返回随机动作（blink/turn_left/turn_right/open_mouth）并展示给用户，但：

1. `check-in` 接口**不接收 challenge_action 参数**，后端不知道应该验证什么动作
2. 后端正提交的图片仅做通用反欺骗分析，**没有针对指定动作的验证逻辑**
3. 用户不做动作、甚至用照片，后端仍然按同样的流程处理

**数据流（当前）**：
```
前端请求挑战 → 后端返回动作文本 → 前端显示"请眨眼"
用户不做任何动作 → 点击完成考勤 → 上传照片 → 后端只做通用防欺骗
通用防欺骗阈值低 → 照片通过 → 签到成功
```

## 优化方案

### 修改 1：提高防欺骗阈值 + 加强反欺骗权重

**文件**：`backend/app/services/liveness_service.py`

- 有 DeepFace 时：threshold 0.38 → **0.55**，DeepFace 权重 56% → **70%**
- 无 DeepFace 时：threshold 0.30 → **0.45**
- 添加 `deepface` 到 `requirements.txt`，设为硬依赖

### 修改 2：后端接收并验证挑战动作

**文件**：`backend/app/services/liveness_service.py`

新增 `verify_action()` 方法，用 YuNet 提供的人脸关键点验证动作：

```
YuNet 检测返回的 15 维向量包含：
  [x, y, w, h, x_re, y_re, x_le, y_le, x_n, y_n, x_rc, y_rc, x_lc, y_lc, angle]
  右眼x  右眼y  左眼x  左眼y  鼻尖x 鼻尖y 右嘴角x 右嘴角y 左嘴角x 左嘴角y
```

利用这些关键点：
- **turn_left**：鼻尖 x 相对人脸框右移（鼻尖 x > 脸框 x + 0.55 * 脸宽）
- **turn_right**：鼻尖 x 相对人脸框左移（鼻尖 x < 脸框 x + 0.45 * 脸宽）
- **open_mouth**：嘴部高度（嘴角到鼻尖距离）与脸高的比例 > 阈值
- **smile**（替换 blink）：使用现有的 Haar 微笑级联分类器检测

**blink 替换为 smile 的原因**：从单张图片无法判断"刚眨过眼"，只能判断"眼睛是否闭着"，而闭眼照片也能通过。微笑可以从单张图可靠检测，且现有代码已有 smile cascade。

**文件**：`backend/app/api/attendance.py`

- `check-in` 接口新增 `challenge_action` 查询参数
- 调用 `liveness_service.verify_action(image, action, face_box)` 
- 验证失败 → 标记为 failed，消息设为"未完成指定动作：请XXX"
- 配合 anti-spoofing，若检测到翻拍则显示"XXX 使用照片签到"

### 修改 3：前端发送 challenge_action

**文件**：`frontend/src/views/Attendance.vue`

- `captureAndSubmit()` 和 `submit()` 中传递当前 `challenge.action`
- `startContinuousLoop` 中的 API 调用同样传递

**文件**：`frontend/src/api/modules.js`

- `checkIn` 方法新增 `challengeAction` 参数

**文件**：`backend/app/api/attendance.py`

- `LIVENESS_ACTIONS` 中的 `"blink"` → `"smile"`，文字改为"请微笑后完成考勤"

### 验证流程

1. 启动后端和前端
2. 开启活体检测
3. 用本人真实人脸签到 → 应成功
4. 用手机照片/打印照片签到 → 应失败，消息含"翻拍识别"或"使用照片签到"
5. 本人真人但不做指定动作 → 应失败，消息含"未完成指定动作"
6. 本人真人 + 完成动作 → 应成功
7. 关闭活体检测 → 不做动作也可签到
