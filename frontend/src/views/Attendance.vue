<template>
  <div class="page">
    <div class="toolbar">
      <h2>考勤识别</h2>
      <div class="toolbar-right">
        <el-input v-model="courseName" class="course-input" placeholder="课程名称" clearable />
        <el-switch
          v-if="auth.role === 'teacher'"
          v-model="livenessEnabled"
          active-text="活体检测"
          inactive-text="活体检测关"
          @change="saveLiveness"
        />
      </div>
    </div>

    <div class="section camera-section">
      <div class="camera-wrapper">
        <video ref="videoRef" class="camera" autoplay muted playsinline @loadedmetadata="onVideoReady" />
        <div v-if="cameraActive" class="face-guide">
          <svg viewBox="0 0 200 260" class="guide-svg">
            <ellipse cx="100" cy="130" rx="75" ry="95" fill="none"
              :stroke="faceDetected ? '#10b981' : 'rgba(255,255,255,0.4)'"
              stroke-width="2.5" stroke-dasharray="6 4"
              class="guide-ellipse" />
          </svg>
          <span class="guide-text" :class="{ detected: faceDetected }">
            {{ faceDetected ? '人脸已检测' : '请将面部对准椭圆区域' }}
          </span>
        </div>
        <canvas ref="overlayRef" class="camera-overlay" v-show="cameraActive" />
        <transition name="manual-prompt-fade">
          <div v-if="manualPromptVisible" class="manual-action-prompt">
            <el-icon><Timer /></el-icon>
            <span>{{ currentChallengeText }}</span>
          </div>
        </transition>
        <div v-if="!cameraActive" class="camera-placeholder">
          <el-icon :size="48"><VideoCamera /></el-icon>
          <p>点击下方按钮开启摄像头</p>
        </div>


        <!-- 连续捕捉状态 -->
        <transition name="status-fade">
          <div v-if="captureStatus" class="capture-status-bar" :class="'status-' + statusType">
            <span class="status-dot" />
            {{ captureStatus }}
          </div>
        </transition>
      </div>

      <!-- 动作进度列表（持久显示直到签到结果） -->
      <div v-if="livenessEnabled && challengeActions.length" class="action-steps">
        <div v-for="(a, i) in challengeActions" :key="a.code"
          :class="['step-row', completedActions.includes(a.code) ? 'step-done' : (i === challengeStep ? 'step-current' : 'step-pending')]">
          <span class="step-icon">{{ completedActions.includes(a.code) ? '✓' : (i === challengeStep ? '▶' : '○') }}</span>
          <span class="step-text">{{ displayChallengeText(a) }}</span>
        </div>
      </div>
      <el-alert
        v-else-if="livenessEnabled"
        title="获取挑战动作…"
        type="info"
        :closable="false"
        show-icon
      />
      <el-alert
        v-else
        title="请保持正脸、光线充足，尽量靠近摄像头"
        type="info"
        :closable="false"
        show-icon
      />

      <!-- 操作按钮 -->
      <div class="actions">
        <el-button :icon="VideoCamera" @click="startCamera">
          {{ cameraActive ? '切换摄像头' : '开启摄像头' }}
        </el-button>
        <el-button :icon="Refresh" :disabled="!livenessEnabled" @click="loadChallenge">
          刷新动作
        </el-button>
        <el-button v-if="cameraActive" type="success" :icon="Check" :loading="loading" class="capture-btn" @click="captureAndSubmit">
          手动捕捉
        </el-button>
<el-button :type="continuousMode ? 'danger' : 'warning'" :icon="VideoCamera" @click="toggleContinuousCapture">
          {{ continuousMode ? '停止捕捉' : '自动捕捉' }}
        </el-button>
      </div>

      <!-- 步骤指示 -->
      <el-steps :active="statusStep" finish-status="success" simple class="steps">
        <el-step title="摄像头" />
        <el-step :title="livenessEnabled ? '活体动作' : '跳过活体'" />
        <el-step title="人脸识别" />
        <el-step title="结果" />
      </el-steps>

      <!-- 结果展示 -->
      <transition name="fade">
        <div v-if="result" class="result-panel">
          <el-alert
            :title="result.message"
            :type="result.success ? 'success' : 'error'"
            show-icon
            :closable="false"
          />
          <el-descriptions v-if="result.record" :column="3" border class="result-box">
            <el-descriptions-item label="学号" :span="1">
              <span style="font-weight:600">{{ result.record.student?.student_no || '-' }}</span>
            </el-descriptions-item>
            <el-descriptions-item label="姓名">
              <span style="font-weight:600">{{ result.record.student?.name || '-' }}</span>
            </el-descriptions-item>
            <el-descriptions-item label="性别">
              {{ result.record.student?.gender || '-' }}
            </el-descriptions-item>
            <el-descriptions-item label="班级">
              {{ result.record.student?.class_name || '-' }}
            </el-descriptions-item>
            <el-descriptions-item label="置信度">
              <span :style="{ color: (result.record.confidence || 0) >= 0.68 ? '#10b981' : '#ef4444', fontWeight: 600 }">
                {{ (result.record.confidence * 100).toFixed(1) }}%
              </span>
            </el-descriptions-item>
            <el-descriptions-item label="情绪">
              <span v-if="result.record.emotion_type && result.record.emotion_type !== 'neutral'" style="white-space: nowrap">
                {{ formatEmotion(result.record.emotion_type) }}
              </span>
              <span v-else>-</span>
            </el-descriptions-item>
            <el-descriptions-item label="活体分">
              {{ result.record.liveness_score?.toFixed(3) }}
            </el-descriptions-item>
            <el-descriptions-item label="课程">{{ result.record.course_name }}</el-descriptions-item>
            <el-descriptions-item label="时间">{{ formatTime(result.record.timestamp) }}</el-descriptions-item>
            <el-descriptions-item label="人脸照片数">
              <el-tag v-if="result.record.student?.face_sample_count" size="small" type="info">
                {{ result.record.student.face_sample_count }} 张
              </el-tag>
              <span v-else>-</span>
            </el-descriptions-item>
          </el-descriptions>
        </div>
      </transition>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Check, Refresh, Timer, VideoCamera } from '@element-plus/icons-vue'
import { attendanceApi } from '../api/modules'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()

const videoRef = ref()
const overlayRef = ref()
const courseName = ref('默认课程')
const loading = ref(false)
const result = ref(null)
const statusStep = ref(0)
const livenessEnabled = ref(false)
const cameraActive = ref(false)
const continuousMode = ref(false)
const captureStatus = ref('')
const statusType = ref('info')
const cooldownCount = ref(0)
let continuousTimer = null
const challengeActions = ref([])
const challengeStep = ref(0)

// 实时人脸检测
const detectionFaces = ref([])
const primaryRecognized = ref(false)
const detecting = ref(false)
let detectTimer = null
const faceDetected = computed(() => detectionFaces.value.length > 0)
const completedActions = ref([])
const currentChallengeAction = computed(() => challengeActions.value[challengeStep.value] || null)
const currentActionCode = computed(() => currentChallengeAction.value?.code || '')
const currentChallengeText = computed(() => displayChallengeText(currentChallengeAction.value))
const manualPromptVisible = computed(() => (
  cameraActive.value
  && livenessEnabled.value
  && !continuousMode.value
  && Boolean(currentChallengeText.value)
))
const AUTO_CAPTURE_INTERVAL_MS = 500
const ACTION_BASELINE_DELAY_MS = 950
const MAX_ACTION_CAPTURE_ATTEMPTS = 2
const ACTION_PROMPT_MAP = {
  smile: '先自然，再微笑',
  turn_head: '先正脸，再转头',
  turn_left: '先正脸，再向左转头',
  turn_right: '先正脸，再向右转头',
  open_mouth: '先闭嘴，再张嘴',
}

let cameraStream = null

const EMOTION_MAP = {
  happy: '😊 Happy',
  sad: '😢 Sad',
  angry: '😠 Angry',
  surprised: '😮 Surprised',
  fearful: '😨 Fearful',
  fear: '😨 Fearful',
  disgusted: '🤢 Disgusted',
  disgust: '🤢 Disgusted',
  neutral: '😐 Neutral',
}

function formatEmotion(type) {
  return EMOTION_MAP[type] || type
}

function formatTime(ts) {
  if (!ts) return '-'
  const d = new Date(ts)
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

async function startCamera() {
  // 清除旧流
  if (cameraStream) {
    cameraStream.getTracks().forEach((t) => t.stop())
    cameraStream = null
    if (detectTimer) {
      clearInterval(detectTimer)
      detectTimer = null
    }
  }
  try {
    cameraStream = await navigator.mediaDevices.getUserMedia({
      video: {
        width: { ideal: 1280 },
        height: { ideal: 720 },
        facingMode: 'user',
      },
      audio: false,
    })
    videoRef.value.srcObject = cameraStream
    cameraActive.value = true
    detectionFaces.value = []
    primaryRecognized.value = false
    statusStep.value = 1
  } catch {
    ElMessage.error('摄像头启动失败，请检查浏览器权限')
  }
}

function onVideoReady() {
  startFaceDetection()
}

function startFaceDetection() {
  if (detectTimer) clearInterval(detectTimer)
  detectTimer = setInterval(async () => {
    if (detecting.value) return
    if (!cameraActive.value) return
    const video = videoRef.value
    if (!video?.videoWidth) return

    detecting.value = true
    try {
      const cap = document.createElement('canvas')
      const scale = 320 / video.videoWidth
      cap.width = 320
      cap.height = Math.round(video.videoHeight * scale)
      cap.getContext('2d').drawImage(video, 0, 0, cap.width, cap.height)
      const blob = await new Promise((r) => cap.toBlob(r, 'image/jpeg', 0.7))
      if (!blob) return
      const { data } = await attendanceApi.detect(new File([blob], 'detect.jpg'))
      detectionFaces.value = data.faces || []
      drawFaceBoxes(detectionFaces.value)
    } catch {
      detectionFaces.value = []
      drawFaceBoxes([])
    } finally {
      detecting.value = false
    }
  }, 250)
}

function drawFaceBoxes(faces) {
  const canvas = overlayRef.value
  const video = videoRef.value
  if (!canvas || !video) return

  canvas.width = video.clientWidth
  canvas.height = video.clientHeight
  const ctx = canvas.getContext('2d')
  ctx.clearRect(0, 0, canvas.width, canvas.height)

  for (const f of faces) {
    const [rx, ry, rw, rh] = f.bbox
    const x = rx * canvas.width
    const y = ry * canvas.height
    const w = rw * canvas.width
    const h = rh * canvas.height
    const color = f.is_primary
      ? (primaryRecognized.value ? '#10b981' : '#f59e0b')
      : '#ef4444'

    ctx.strokeStyle = color
    ctx.lineWidth = 2.5
    ctx.strokeRect(x, y, w, h)
  }
}

async function submit(file) {
  loading.value = true
  statusStep.value = 2
  result.value = null
  try {
    const { data } = await attendanceApi.checkIn(file, courseName.value, currentActionCode.value)
    result.value = data
    statusStep.value = 4
    if (data.success) {
      primaryRecognized.value = true
      ElMessage.success(data.message)
    } else {
      primaryRecognized.value = false
      ElMessage.error(data.message)
    }
    await refreshChallengeAfterCheckIn()
  } finally {
    loading.value = false
  }
}

function displayChallengeText(action) {
  if (!action) return ''
  return ACTION_PROMPT_MAP[action.code] || (action.text || '').replace(/后完成考勤$/, '')
}

function wait(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

function captureFrameBlob(video, quality = 0.95) {
  const cvs = document.createElement('canvas')
  cvs.width = video.videoWidth
  cvs.height = video.videoHeight
  cvs.getContext('2d').drawImage(video, 0, 0)
  return new Promise((resolve) => {
    cvs.toBlob(resolve, 'image/jpeg', quality)
  })
}

async function refreshChallengeAfterCheckIn() {
  if (!livenessEnabled.value) return
  try {
    await loadChallenge()
  } catch {
    ElMessage.warning('活体动作刷新失败，请手动刷新')
  }
}

async function captureAndSubmit() {
  const video = videoRef.value
  if (!video?.videoWidth) {
    ElMessage.warning('请先开启摄像头')
    return
  }

  loading.value = true

  // Phase 1: 多步骤动作验证。每步只做有限采样，避免自动扫描视频帧命中。
  if (livenessEnabled.value && challengeActions.value.length > 0) {
    statusStep.value = 2
    while (challengeStep.value < challengeActions.value.length) {
      const action = challengeActions.value[challengeStep.value]
      const baselineBlob = await captureFrameBlob(video)
      if (!baselineBlob) break

      try {
        await attendanceApi.verifyAction(baselineBlob, action.code)
      } catch {
        ElMessage.warning('基线采集失败，请重新开始')
        loading.value = false
        return
      }

      await wait(ACTION_BASELINE_DELAY_MS)

      let passed = false
      for (let attempt = 0; attempt < MAX_ACTION_CAPTURE_ATTEMPTS; attempt++) {
        const actionBlob = await captureFrameBlob(video)
        if (!actionBlob) break
        try {
          const verifyRes = await attendanceApi.verifyAction(actionBlob, action.code)
          if (verifyRes.data.passed) {
            passed = true
            break
          }
        } catch {
          // 失败后进入下一次有限尝试
        }
        if (attempt + 1 < MAX_ACTION_CAPTURE_ATTEMPTS) {
          await wait(650)
        }
      }

      if (passed) {
        if (!completedActions.value.includes(action.code)) {
          completedActions.value.push(action.code)
        }
        challengeStep.value++
      } else {
        ElMessage.warning('活体动作未完成，请按提示重新开始')
        await loadChallenge()
        loading.value = false
        return
      }
    }
  }

  // Phase 2: 签到拍照
  statusStep.value = 3
  const canvas = document.createElement('canvas')
  canvas.width = video.videoWidth
  canvas.height = video.videoHeight
  canvas.getContext('2d').drawImage(video, 0, 0, canvas.width, canvas.height)
  canvas.toBlob((blob) => {
    if (!blob) {
      ElMessage.error('拍照失败')
      loading.value = false
      return
    }
    submit(new File([blob], 'check-in.jpg', { type: 'image/jpeg' }))
  }, 'image/jpeg', 0.95)
}

async function loadChallenge() {
  const { data } = await attendanceApi.challenge()
  challengeActions.value = data.actions || []
  challengeStep.value = 0
  completedActions.value = []
  primaryRecognized.value = false
  livenessEnabled.value = Boolean(data.enabled)
  statusStep.value = Math.max(statusStep.value, 1)
}

async function loadLivenessSettings() {
  const { data } = await attendanceApi.livenessSettings()
  livenessEnabled.value = data.enabled
  await loadChallenge()
}

async function saveLiveness(value) {
  const { data } = await attendanceApi.updateLivenessSettings(value)
  livenessEnabled.value = data.enabled
  await loadChallenge()
  ElMessage.success(data.enabled ? '活体检测已开启' : '活体检测已关闭')
}

async function toggleContinuousCapture() {
  if (!continuousMode.value && livenessEnabled.value) {
    ElMessage.warning('活体检测开启时请使用手动捕捉')
    return
  }

  if (continuousMode.value) {
    continuousMode.value = false
    if (continuousTimer) {
      clearInterval(continuousTimer)
      continuousTimer = null
    }
    captureStatus.value = ''
    cooldownCount.value = 0
    primaryRecognized.value = false
    statusStep.value = 1
    return
  }

  if (!cameraActive.value) await startCamera()
  continuousMode.value = true
  captureStatus.value = '等待人脸…'
  statusType.value = 'info'
  startContinuousLoop()
}

function startContinuousLoop() {
  let processing = false
  let nextAttemptAt = 0

  continuousTimer = setInterval(() => {
    if (!continuousMode.value) return
    if (cooldownCount.value > 0) return
    if (processing) return
    if (Date.now() < nextAttemptAt) return

    if (!faceDetected.value) {
      captureStatus.value = '等待人脸…'
      statusType.value = 'info'
      return
    }

    const video = videoRef.value
    if (!video?.videoWidth) return

    processing = true
    statusStep.value = 2

    const canvas = document.createElement('canvas')
    canvas.width = video.videoWidth
    canvas.height = video.videoHeight
    canvas.getContext('2d').drawImage(video, 0, 0)

    canvas.toBlob(async (blob) => {
      try {
        if (!blob || !continuousMode.value) return

        // Phase 1: multi-step action verification
        if (livenessEnabled.value && challengeActions.value.length > 0) {
          const step = challengeStep.value
          // 所有动作已完成 → 进入签到
          if (step >= challengeActions.value.length) {
            captureStatus.value = '所有动作完成，正在签到…'
            statusType.value = 'success'
          } else {
            const action = challengeActions.value[step]
            const actionPrompt = displayChallengeText(action)
            captureStatus.value = actionPrompt
            statusType.value = 'warning'

            try {
              const verifyRes = await attendanceApi.verifyAction(blob, action.code, { silentError: true })
              if (!verifyRes.data.passed) {
                captureStatus.value = actionPrompt
                nextAttemptAt = Date.now() + AUTO_CAPTURE_INTERVAL_MS
                return
              }
              // 动作通过 — 保留当前提示直到下次循环更新
              completedActions.value.push(action.code)
              challengeStep.value++
              return
            } catch {
              captureStatus.value = actionPrompt
              statusType.value = 'warning'
              nextAttemptAt = Date.now() + AUTO_CAPTURE_INTERVAL_MS
              return
            }
          }
        }

        // Phase 2: full check-in
        captureStatus.value = '识别中…'
        statusType.value = 'info'
        statusStep.value = 3

        const { data } = await attendanceApi.checkIn(
          new File([blob], 'check-in.jpg', { type: 'image/jpeg' }),
          courseName.value,
          currentActionCode.value,
          { silentError: true }
        )
        result.value = data
        statusStep.value = 4

        if (data.success) {
          primaryRecognized.value = true
          captureStatus.value = `签到成功：${data.record?.student?.name || '✓'}`
          statusType.value = 'success'
        } else {
          primaryRecognized.value = false
          captureStatus.value = data.message?.length > 30 ? '签到失败' : data.message
          statusType.value = 'error'
        }

        // 刷新挑战动作，下一轮需重新完成
        await refreshChallengeAfterCheckIn()
        await startCooldown()
      } catch {
        captureStatus.value = '请求失败，稍后重试'
        statusType.value = 'error'
        nextAttemptAt = Date.now() + AUTO_CAPTURE_INTERVAL_MS
        await wait(AUTO_CAPTURE_INTERVAL_MS)
      } finally {
        processing = false
      }
    }, 'image/jpeg', 0.95)
  }, AUTO_CAPTURE_INTERVAL_MS)
}

function startCooldown() {
  return new Promise((resolve) => {
    cooldownCount.value = 3
    const timer = setInterval(() => {
      cooldownCount.value--
      if (cooldownCount.value > 0) {
        captureStatus.value = `冷却中 ${cooldownCount.value}s…`
        statusType.value = 'info'
      } else {
        clearInterval(timer)
        captureStatus.value = '等待人脸…'
        statusType.value = 'info'
        resolve()
      }
    }, 1000)
  })
}

onMounted(loadLivenessSettings)

onBeforeUnmount(() => {
  if (continuousTimer) clearInterval(continuousTimer)
  if (detectTimer) clearInterval(detectTimer)
  cameraStream?.getTracks().forEach((t) => t.stop())
})
</script>

<style scoped>
.toolbar-right,
.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
}

.course-input {
  width: 220px;
}

.camera-section {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.camera-wrapper {
  position: relative;
  width: min(100%, 860px);
  aspect-ratio: 16 / 9;
  border-radius: 10px;
  overflow: hidden;
  background: #111827;
  align-self: center;
}

.camera {
  width: 100%;
  height: 100%;
  display: block;
  object-fit: cover;
}

.camera-overlay {
  position: absolute;
  inset: 0;
  pointer-events: none;
}

.camera-placeholder {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: rgba(255, 255, 255, 0.4);
  gap: 12px;
}

.camera-placeholder p {
  margin: 0;
  font-size: 14px;
}

.manual-action-prompt {
  position: absolute;
  top: 18px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 12;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 18px;
  border-radius: 22px;
  background: rgba(245, 158, 11, 0.92);
  color: #fff;
  font-size: 16px;
  font-weight: 700;
  white-space: nowrap;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.22);
  backdrop-filter: blur(6px);
  pointer-events: none;
}

.manual-action-prompt .el-icon {
  font-size: 18px;
}

.manual-prompt-fade-enter-active,
.manual-prompt-fade-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.manual-prompt-fade-enter-from,
.manual-prompt-fade-leave-to {
  opacity: 0;
  transform: translateX(-50%) translateY(-8px);
}

.face-guide {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  pointer-events: none;
}

.guide-svg {
  width: 180px;
  height: 240px;
}

.guide-ellipse {
  transition: stroke 0.3s ease;
}

.guide-text {
  position: absolute;
  bottom: 18%;
  font-size: 13px;
  color: rgba(255, 255, 255, 0.6);
  background: rgba(0, 0, 0, 0.5);
  padding: 4px 14px;
  border-radius: 20px;
  transition: all 0.3s ease;
  white-space: nowrap;
}

.guide-text.detected {
  color: #10b981;
  background: rgba(16, 185, 129, 0.15);
}

.actions {
  margin: 4px 0;
}

.capture-btn {
  font-weight: 600;
  padding: 10px 22px;
}

.steps {
  margin-bottom: 4px;
}

.result-box {
  margin-top: 12px;
}

.result-panel {
  animation: fadeIn 0.3s ease;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}

/* 自动拍照倒计时 */

/* 连续捕捉状态条 */
.capture-status-bar {
  position: absolute;
  left: 50%;
  bottom: 16px;
  transform: translateX(-50%);
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 18px;
  border-radius: 20px;
  font-size: 14px;
  font-weight: 600;
  white-space: nowrap;
  z-index: 11;
  backdrop-filter: blur(6px);
  pointer-events: none;
}
.capture-status-bar.status-info {
  background: rgba(107, 114, 128, 0.85);
  color: #fff;
}
.capture-status-bar.status-success {
  background: rgba(16, 185, 129, 0.9);
  color: #fff;
}
.capture-status-bar.status-error {
  background: rgba(239, 68, 68, 0.9);
  color: #fff;
}
.capture-status-bar.status-warning {
  background: rgba(245, 158, 11, 0.9);
  color: #fff;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: currentColor;
  animation: statusPulse 1.2s ease-in-out infinite;
}

@keyframes statusPulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}

.status-fade-enter-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}
.status-fade-leave-active {
  transition: opacity 0.15s ease;
}
.status-fade-enter-from {
  opacity: 0;
  transform: translateX(-50%) translateY(8px);
}
.status-fade-leave-to {
  opacity: 0;
}

/* 动作步骤进度 */
.action-steps {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 12px 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.step-row {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 14px;
  transition: all 0.3s ease;
}
.step-icon {
  width: 22px;
  text-align: center;
  font-size: 14px;
  flex-shrink: 0;
}
.step-text {
  flex: 1;
}
.step-pending {
  color: #94a3b8;
}
.step-current {
  color: #1e293b;
  font-weight: 600;
}
.step-current .step-icon {
  color: #f59e0b;
}
.step-done {
  color: #10b981;
}
.step-done .step-icon {
  font-weight: 700;
}
</style>
