<template>
  <div class="page">
    <div class="toolbar">
      <h2>考勤识别</h2>
      <div class="toolbar-right">
        <el-input v-model="courseName" class="course-input" placeholder="课程名称" clearable />
        <el-switch
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
        <canvas ref="overlayRef" class="camera-overlay" v-show="cameraActive" />
        <!-- 人脸引导框 -->
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
        <div v-else class="camera-placeholder">
          <el-icon :size="48"><VideoCamera /></el-icon>
          <p>点击下方按钮开启摄像头</p>
        </div>

        <!-- 倒计时 overlay -->
        <transition name="countdown-fade">
          <div v-if="countdown > 0" class="countdown-overlay">
            <svg class="countdown-ring" viewBox="0 0 100 100">
              <circle class="countdown-bg" cx="50" cy="50" r="44" />
              <circle
                class="countdown-progress"
                cx="50" cy="50" r="44"
                :style="{ strokeDashoffset: 276 * (1 - countdown / countdownTotal) }"
              />
            </svg>
            <span class="countdown-number">{{ countdown }}</span>
          </div>
        </transition>

        <!-- 连续捕捉状态 -->
        <transition name="status-fade">
          <div v-if="captureStatus" class="capture-status-bar" :class="'status-' + statusType">
            <span class="status-dot" />
            {{ captureStatus }}
          </div>
        </transition>
      </div>

      <!-- 提示 -->
      <el-alert
        v-if="livenessEnabled && challenge.text"
        :title="challenge.text"
        type="warning"
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
          完成考勤
        </el-button>
        <el-button :icon="Timer" :disabled="autoCapturing" @click="autoCapture">
          3 秒自动拍照
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
              <span v-if="result.record.emotion_type && result.record.emotion_type !== 'neutral'">
                {{ emotionIcon(result.record.emotion_type) }}
                {{ result.record.emotion_type }}
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
import { onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Check, Refresh, Timer, VideoCamera } from '@element-plus/icons-vue'
import { attendanceApi } from '../api/modules'

const videoRef = ref()
const overlayRef = ref()
const courseName = ref('默认课程')
const loading = ref(false)
const result = ref(null)
const statusStep = ref(0)
const autoCapturing = ref(false)
const livenessEnabled = ref(false)
const cameraActive = ref(false)
const faceDetected = ref(false)
const countdown = ref(0)
const countdownTotal = ref(3)
const continuousMode = ref(false)
const captureStatus = ref('')
const statusType = ref('info')
const cooldownCount = ref(0)
let continuousTimer = null
const challenge = reactive({ action: '', text: '' })

let cameraStream = null
let detectInterval = null

const EMOTION_ICONS = {
  happy: '😊',
  sad: '😢',
  angry: '😠',
  surprised: '😮',
  fearful: '😨',
  disgusted: '🤢',
  neutral: '😐',
}

function emotionIcon(type) {
  return EMOTION_ICONS[type] || ''
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
    if (detectInterval) {
      clearInterval(detectInterval)
      detectInterval = null
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
    faceDetected.value = false
    statusStep.value = 1
  } catch {
    ElMessage.error('摄像头启动失败，请检查浏览器权限')
  }
}

function onVideoReady() {
  // 简单人脸检测模拟：基于运动检测或亮度来判断画面中是否有人
  // 实际应用中可用更复杂的方法，此处用亮度变化简单判断
  startFaceDetection()
}

function startFaceDetection() {
  if (detectInterval) clearInterval(detectInterval)
  detectInterval = setInterval(() => {
    const video = videoRef.value
    if (!video?.videoWidth) return
    // 取中心区域亮度方差判断是否有面部（非精确，仅用于引导提示）
    const canvas = document.createElement('canvas')
    canvas.width = 160
    canvas.height = 120
    const ctx = canvas.getContext('2d')
    ctx.drawImage(video, 0, 0, 160, 120)
    const imageData = ctx.getImageData(0, 0, 160, 120)
    const pixels = imageData.data
    let sum = 0
    for (let i = 0; i < pixels.length; i += 4) {
      sum += pixels[i] * 0.299 + pixels[i + 1] * 0.587 + pixels[i + 2] * 0.114
    }
    const avg = sum / (pixels.length / 4)
    // 计算中心区域方差（人脸通常有对比度）
    let variance = 0
    for (let i = 0; i < pixels.length; i += 4) {
      const gray = pixels[i] * 0.299 + pixels[i + 1] * 0.587 + pixels[i + 2] * 0.114
      variance += (gray - avg) ** 2
    }
    variance /= pixels.length / 4
    faceDetected.value = variance > 1500 && avg > 30 && avg < 230
  }, 500)
}

async function submit(file) {
  loading.value = true
  statusStep.value = 2
  result.value = null
  try {
    const { data } = await attendanceApi.checkIn(file, courseName.value)
    result.value = data
    statusStep.value = 4
    if (data.success) {
      ElMessage.success(data.message)
    } else {
      ElMessage.error(data.message)
    }
  } finally {
    loading.value = false
  }
}

function captureAndSubmit() {
  const video = videoRef.value
  if (!video?.videoWidth) {
    ElMessage.warning('请先开启摄像头')
    return
  }
  const canvas = document.createElement('canvas')
  canvas.width = video.videoWidth
  canvas.height = video.videoHeight
  canvas.getContext('2d').drawImage(video, 0, 0, canvas.width, canvas.height)
  canvas.toBlob((blob) => {
    if (!blob) {
      ElMessage.error('拍照失败')
      return
    }
    submit(new File([blob], 'check-in.jpg', { type: 'image/jpeg' }))
  }, 'image/jpeg', 0.95)
}

async function loadChallenge() {
  const { data } = await attendanceApi.challenge()
  Object.assign(challenge, data)
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

async function autoCapture() {
  if (!videoRef.value?.videoWidth) await startCamera()
  autoCapturing.value = true
  statusStep.value = 2
  countdownTotal.value = 3
  countdown.value = 3
  const timer = setInterval(() => {
    countdown.value--
    if (countdown.value <= 0) {
      clearInterval(timer)
      autoCapturing.value = false
      captureAndSubmit()
    }
  }, 1000)
}

async function toggleContinuousCapture() {
  if (continuousMode.value) {
    continuousMode.value = false
    if (continuousTimer) {
      clearInterval(continuousTimer)
      continuousTimer = null
    }
    captureStatus.value = ''
    cooldownCount.value = 0
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
  continuousTimer = setInterval(() => {
    if (!continuousMode.value) return
    if (cooldownCount.value > 0) return

    if (!faceDetected.value) {
      captureStatus.value = '等待人脸…'
      statusType.value = 'info'
      return
    }

    const video = videoRef.value
    if (!video?.videoWidth) return

    captureStatus.value = '检测中…'
    statusType.value = 'warning'
    statusStep.value = 2

    const canvas = document.createElement('canvas')
    canvas.width = video.videoWidth
    canvas.height = video.videoHeight
    canvas.getContext('2d').drawImage(video, 0, 0)

    canvas.toBlob(async (blob) => {
      if (!blob || !continuousMode.value) return

      captureStatus.value = '识别中…'
      statusType.value = 'info'
      statusStep.value = 3

      try {
        const { data } = await attendanceApi.checkIn(
          new File([blob], 'check-in.jpg', { type: 'image/jpeg' }),
          courseName.value
        )
        result.value = data
        statusStep.value = 4

        if (data.success) {
          captureStatus.value = `签到成功：${data.record?.student?.name || '✓'}`
          statusType.value = 'success'
        } else {
          captureStatus.value = data.message?.length > 30 ? '签到失败' : data.message
          statusType.value = 'error'
        }
      } catch {
        captureStatus.value = '请求失败'
        statusType.value = 'error'
      }

      await startCooldown()
    }, 'image/jpeg', 0.95)
  }, 800)
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
  if (detectInterval) clearInterval(detectInterval)
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

/* 人脸引导框 */
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
.countdown-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.55);
  z-index: 10;
}

.countdown-ring {
  width: 96px;
  height: 96px;
  transform: rotate(-90deg);
}

.countdown-bg {
  fill: none;
  stroke: rgba(255, 255, 255, 0.15);
  stroke-width: 5;
}

.countdown-progress {
  fill: none;
  stroke: #10b981;
  stroke-width: 5;
  stroke-linecap: round;
  stroke-dasharray: 276;
  transition: stroke-dashoffset 0.9s linear;
}

.countdown-number {
  position: absolute;
  font-size: 40px;
  font-weight: 700;
  color: #fff;
  text-shadow: 0 2px 8px rgba(0, 0, 0, 0.4);
  user-select: none;
}

.countdown-fade-enter-active {
  transition: opacity 0.25s ease;
}
.countdown-fade-leave-active {
  transition: opacity 0.2s ease;
}
.countdown-fade-enter-from,
.countdown-fade-leave-to {
  opacity: 0;
}

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
</style>
