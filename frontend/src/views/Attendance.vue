<template>
  <div class="page">
    <div class="toolbar">
      <h2>考勤签到</h2>
      <div class="toolbar-right">
        <el-select v-model="selectedSessionId" placeholder="选择考勤活动" clearable style="width: 220px; margin-right: 8px">
          <el-option v-for="s in sessions" :key="s.id" :label="`${s.course_name} ${s.date} ${s.session_no}`" :value="s.id" />
        </el-select>
        <el-switch v-model="livenessEnabled" active-text="活体" inactive-text="关" @change="saveLiveness" />
      </div>
    </div>

    <div class="camera-section">
      <div class="camera-wrapper">
        <video ref="videoRef" class="camera" autoplay muted playsinline />
        <canvas ref="overlayRef" class="camera-overlay" />
        <div v-if="!cameraActive" class="camera-placeholder">
          <el-icon :size="48"><VideoCamera /></el-icon>
          <p>点击下方按钮开启摄像头</p>
        </div>
<<<<<<< Updated upstream
        <!-- 倒计时 -->
        <transition name="countdown-fade">
          <div v-if="countdown > 0" class="countdown-overlay">
            <svg class="countdown-ring" viewBox="0 0 100 100">
              <circle class="countdown-bg" cx="50" cy="50" r="44" />
              <circle class="countdown-progress" cx="50" cy="50" r="44"
                :style="{ strokeDashoffset: 276 * (1 - countdown / countdownTotal) }" />
            </svg>
            <span class="countdown-number">{{ countdown }}</span>
          </div>
        </transition>
        <!-- 识别状态 -->
        <div v-if="cameraActive && mode === 'realtime'" class="recognize-status" :class="recognized ? 'ok' : 'waiting'">
          {{ recognized ? `已识别：${recognizedName} ${recogConfidence}%` : '等待识别…' }}
=======

        <!-- 连续捕捉状态 -->
        <transition name="status-fade">
          <div v-if="captureStatus" class="capture-status-bar" :class="'status-' + statusType">
            <span class="status-dot" />
            {{ captureStatus }}
          </div>
        </transition>
      </div>

      <!-- 顺序错误提示 -->
      <div v-if="orderError" class="order-error">
        <el-icon><WarningFilled /></el-icon>
        <span>{{ orderError }}</span>
      </div>

      <!-- 动作进度列表 -->
      <div v-if="livenessEnabled && challengeActions.length" class="action-steps">
        <div v-for="(a, i) in challengeActions" :key="i"
          :class="['step-row', i < challengeStep ? 'step-done' : (i === challengeStep ? 'step-current' : 'step-pending')]">
          <span class="step-icon">{{ i < challengeStep ? '✓' : (i === challengeStep ? '▶' : '○') }}</span>
          <span class="step-text">{{ displayChallengeText(a) }}</span>
>>>>>>> Stashed changes
        </div>
      </div>

      <!-- 提示 -->
      <el-alert v-if="livenessEnabled && challenge.text" :title="challenge.text" type="warning" :closable="false" show-icon />
      <el-alert v-else title="请保持正脸、光线充足" type="info" :closable="false" show-icon />

      <!-- 操作 -->
      <div class="actions">
        <el-button :icon="VideoCamera" @click="startCamera">{{ cameraActive ? '切换' : '开摄像头' }}</el-button>
        <el-radio-group v-model="mode" :disabled="!cameraActive">
          <el-radio-button value="snapshot">3秒拍照</el-radio-button>
          <el-radio-button value="realtime">实时识别</el-radio-button>
        </el-radio-group>
        <el-button v-if="mode === 'snapshot'" type="success" :loading="loading" @click="snapshotCapture">3秒拍照</el-button>
        <el-button v-if="mode === 'realtime'" type="success" :disabled="!recognized" :loading="loading" @click="submitCheckIn">提交考勤</el-button>
      </div>

      <!-- 结果 -->
      <transition name="fade">
        <div v-if="result" class="result-panel">
          <el-alert :title="result.message" :type="result.success ? 'success' : 'error'" show-icon :closable="false" />
          <el-descriptions v-if="result.record" :column="3" border>
            <el-descriptions-item label="学号"><b>{{ result.record.student?.student_no || '-' }}</b></el-descriptions-item>
            <el-descriptions-item label="姓名"><b>{{ result.record.student?.name || '-' }}</b></el-descriptions-item>
            <el-descriptions-item label="置信度">
              <span :style="{ color: (result.record.confidence||0) >= 0.68 ? '#10b981' : '#ef4444' }">{{ (result.record.confidence * 100).toFixed(1) }}%</span>
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
<<<<<<< Updated upstream
import { Check, VideoCamera } from '@element-plus/icons-vue'
import { attendanceApi, sessionApi } from '../api/modules'
=======
import { Check, Refresh, Timer, VideoCamera, WarningFilled } from '@element-plus/icons-vue'
import { attendanceApi } from '../api/modules'
import { useAuthStore } from '../stores/auth'
>>>>>>> Stashed changes

const videoRef = ref(null)
const overlayRef = ref(null)
const mode = ref('realtime')
const loading = ref(false)
const result = ref(null)
const cameraActive = ref(false)
<<<<<<< Updated upstream
const recognized = ref(false)
const recognizedName = ref('')
const recogConfidence = ref(0)
const countdown = ref(0)
const countdownTotal = ref(3)
const livenessEnabled = ref(false)
const selectedSessionId = ref(null)
const sessions = ref([])
const challenge = reactive({ action: '', text: '' })
=======
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
const orderError = ref('')
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
const ACTION_PROMPT_MAP = {
  smile: '请微笑',
  turn_head: '请左右转头',
  open_mouth: '请张嘴',
}

>>>>>>> Stashed changes
let cameraStream = null
let recogTimer = null
let lastRecognizeFile = null
let recogBusy = false

function emotionIcon(t) { return ({ happy:'😊',sad:'😢',angry:'😠',surprised:'😮',fearful:'😨',disgusted:'🤢',neutral:'😐' })[t]||'' }
function formatTime(ts) { if(!ts) return '-'; const d=new Date(ts); const pad=n=>String(n).padStart(2,'0'); return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}` }

async function startCamera() {
  if (cameraStream) { cameraStream.getTracks().forEach(t => t.stop()); cameraStream = null }
  try {
    cameraStream = await navigator.mediaDevices.getUserMedia({ video: { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: 'user' }, audio: false })
    videoRef.value.srcObject = cameraStream
    cameraActive.value = true
    if (mode.value === 'realtime') startRecognition()
    await loadSessions()
  } catch { ElMessage.error('摄像头启动失败') }
}

function stopRecognition() { if (recogTimer) { clearInterval(recogTimer); recogTimer = null } }

function startRecognition() {
  stopRecognition()
  // 快速检测画框：80ms
  recogTimer = setInterval(() => {
    if (!cameraActive.value || mode.value !== 'realtime') return
    detectAndDraw()
  }, 80)
  // 身份匹配：600ms
  setInterval(() => {
    if (!cameraActive.value || mode.value !== 'realtime' || recogBusy) return
    checkIdentity()
  }, 600)
}

function captureFrame(callback, quality = 0.5) {
  const video = videoRef.value; if (!video?.videoWidth) return
  const scale = Math.min(1, 640 / Math.max(video.videoWidth, video.videoHeight))
  const canvas = document.createElement('canvas')
  canvas.width = Math.round(video.videoWidth * scale)
  canvas.height = Math.round(video.videoHeight * scale)
  canvas.getContext('2d').drawImage(video, 0, 0, canvas.width, canvas.height)
  canvas.toBlob(callback, 'image/jpeg', quality)
}

function detectAndDraw() {
  captureFrame(async (blob) => {
    if (!blob) return
    try {
      const { data } = await attendanceApi.detect(new File([blob], 'd.jpg', { type: 'image/jpeg' }))
      drawFaceBoxes(data.faces)
    } catch {}
  }, 0.4)
}

function checkIdentity() {
  recogBusy = true
  captureFrame(async (blob) => {
    if (!blob) { recogBusy = false; return }
    lastRecognizeFile = new File([blob], 'r.jpg', { type: 'image/jpeg' })
    try {
      const { data } = await attendanceApi.recognize(lastRecognizeFile)
      recognized.value = data.matched
      if (data.matched) {
        const mf = data.faces.find(f => f.matched && f.student)
        if (mf) { recognizedName.value = mf.student.name; recogConfidence.value = (mf.confidence * 100).toFixed(1) }
      }
      // 用识别结果更新框的颜色
      drawFaceBoxes(data.faces)
    } catch { recognized.value = false }
    recogBusy = false
  }, 0.5)
}

function drawFaceBoxes(faces) {
<<<<<<< Updated upstream
  const canvas = overlayRef.value; const video = videoRef.value
  if (!canvas || !video?.videoWidth) return
  canvas.width = video.videoWidth; canvas.height = video.videoHeight
  const ctx = canvas.getContext('2d'); ctx.clearRect(0, 0, canvas.width, canvas.height)
  faces.forEach((f, i) => {
    const [x, y, w, h] = f.bbox; const color = f.matched ? '#10b981' : '#f59e0b'
    ctx.strokeStyle = color; ctx.lineWidth = 2; ctx.strokeRect(x, y, w, h)
    if (f.student) { ctx.fillStyle = color; ctx.font = '14px sans-serif'; ctx.fillText(f.student.name, x, y - 4) }
=======
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

  // Phase 1: 多步骤动作验证（与自动捕捉一致）
  if (livenessEnabled.value && challengeActions.value.length > 0) {
    statusStep.value = 2
    while (challengeStep.value < challengeActions.value.length) {
      const action = challengeActions.value[challengeStep.value]
      const cvs = document.createElement('canvas')
      cvs.width = video.videoWidth
      cvs.height = video.videoHeight
      cvs.getContext('2d').drawImage(video, 0, 0)

      const blob = await new Promise((resolve) => {
        cvs.toBlob(resolve, 'image/jpeg', 0.95)
      })
      if (!blob) break

      try {
        const verifyRes = await attendanceApi.verifyAction(blob, action.code)
        if (verifyRes.data.passed) {
          challengeStep.value++
          orderError.value = ''
        } else {
          const stage = verifyRes.data.stage
          if (stage === 'error') {
            challengeStep.value = 0
            orderError.value = verifyRes.data.message
            ElMessage.warning(verifyRes.data.message)
          }
          // hold / cooldown / detect → 继续循环，不重置
        }
      } catch {
        // 忽略网络错误，继续下一帧检测
      }

      if (challengeStep.value < challengeActions.value.length) {
        await new Promise((r) => setTimeout(r, 300))
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
  orderError.value = ''
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
                const d = verifyRes.data
                const stage = d.stage || (d.message?.includes('顺序') ? 'error' : 'detect')
                captureStatus.value = d.message
                if (stage === 'error') {
                  challengeStep.value = 0
                  orderError.value = d.message
                  statusType.value = 'error'
                  nextAttemptAt = Date.now() + 1200
                } else if (stage === 'hold') {
                  statusType.value = 'success'
                } else if (stage === 'cooldown') {
                  statusType.value = 'info'
                } else {
                  statusType.value = 'warning'
                }
                nextAttemptAt = Date.now() + AUTO_CAPTURE_INTERVAL_MS
                return
              }
              // 动作通过
              challengeStep.value++
              orderError.value = ''
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
>>>>>>> Stashed changes
  })
}

async function snapshotCapture() {
  countdownTotal.value = 3; countdown.value = 3
  const timer = setInterval(() => { countdown.value--; if (countdown.value <= 0) clearInterval(timer) }, 1000)
  await new Promise(r => setTimeout(r, 3100))
  const video = videoRef.value; if (!video?.videoWidth) return
  const canvas = document.createElement('canvas'); canvas.width = video.videoWidth; canvas.height = video.videoHeight
  canvas.getContext('2d').drawImage(video, 0, 0)
  canvas.toBlob(async (blob) => {
    if (!blob) return
    lastRecognizeFile = new File([blob], 'snap.jpg', { type: 'image/jpeg' })
    // 定格
    videoRef.value.pause()
    await submitCheckIn()
  }, 'image/jpeg', 0.95)
}

async function submitCheckIn() {
  if (!lastRecognizeFile) {
    // no file yet, capture one
    const video = videoRef.value; if (!video?.videoWidth) return
    const canvas = document.createElement('canvas'); canvas.width = video.videoWidth; canvas.height = video.videoHeight
    canvas.getContext('2d').drawImage(video, 0, 0)
    await new Promise(r => canvas.toBlob(async (blob) => {
      lastRecognizeFile = new File([blob], 'check.jpg', { type: 'image/jpeg' }); r()
    }, 'image/jpeg', 0.95))
  }
  loading.value = true; result.value = null
  try {
    const { data } = await attendanceApi.checkIn(lastRecognizeFile, '默认课程', selectedSessionId.value, challenge.action)
    result.value = data
    if (data.success) { ElMessage.success(data.message) } else { ElMessage.error(data.message) }
  } finally {
    loading.value = false
    if (videoRef.value) videoRef.value.play()
    recognized.value = false
  }
}

async function loadSessions() { try { const { data } = await sessionApi.listActive(); sessions.value = data } catch {} }
async function loadChallenge() { const { data } = await attendanceApi.challenge(); Object.assign(challenge, data); livenessEnabled.value = Boolean(data.enabled) }
async function loadLiveness() { const { data } = await attendanceApi.livenessSettings(); livenessEnabled.value = data.enabled; await loadChallenge() }
async function saveLiveness(v) { await attendanceApi.updateLivenessSettings(v); await loadChallenge() }

onMounted(() => { loadLiveness(); loadSessions() })
onBeforeUnmount(() => { stopRecognition(); if (cameraStream) cameraStream.getTracks().forEach(t => t.stop()) })
</script>

<style scoped>
<<<<<<< Updated upstream
.toolbar-right, .actions { display: flex; flex-wrap: wrap; gap: 10px; align-items: center }
.camera-section { display: flex; flex-direction: column; gap: 14px }
.camera-wrapper { position: relative; width: min(100%, 860px); aspect-ratio: 16/9; border-radius: 10px; overflow: hidden; background: #111827; align-self: center }
.camera, .camera-overlay { width: 100%; height: 100%; display: block; object-fit: cover; position: absolute; inset: 0 }
.camera-overlay { z-index: 5; pointer-events: none }
.camera-placeholder { position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; color: rgba(255,255,255,0.4); gap: 12px }
.recognize-status { position: absolute; left: 12px; top: 12px; z-index: 10; padding: 4px 14px; border-radius: 20px; font-size: 14px; font-weight: 600; color: #fff }
.recognize-status.waiting { background: rgba(107,114,128,0.85) }
.recognize-status.ok { background: rgba(16,185,129,0.9) }
.countdown-overlay { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; background: rgba(0,0,0,0.55); z-index: 10 }
.countdown-ring { width: 96px; height: 96px; transform: rotate(-90deg) }
.countdown-bg { fill: none; stroke: rgba(255,255,255,0.15); stroke-width: 5 }
.countdown-progress { fill: none; stroke: #10b981; stroke-width: 5; stroke-linecap: round; stroke-dasharray: 276; transition: stroke-dashoffset 0.9s linear }
.countdown-number { position: absolute; font-size: 40px; font-weight: 700; color: #fff; text-shadow: 0 2px 8px rgba(0,0,0,0.4) }
.countdown-fade-enter-active { transition: opacity 0.25s ease }
.countdown-fade-leave-active { transition: opacity 0.2s ease }
.countdown-fade-enter-from, .countdown-fade-leave-to { opacity: 0 }
.result-panel { animation: fadeIn 0.3s ease }
@keyframes fadeIn { from { opacity: 0; transform: translateY(8px) } to { opacity: 1; transform: translateY(0) } }
=======
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

.order-error {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  background: #fef3c7;
  border: 1px solid #fcd34d;
  border-radius: 6px;
  color: #92400e;
  font-size: 13px;
  font-weight: 500;
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
>>>>>>> Stashed changes
</style>
