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
import { Check, VideoCamera } from '@element-plus/icons-vue'
import { attendanceApi, sessionApi } from '../api/modules'

const videoRef = ref(null)
const overlayRef = ref(null)
const mode = ref('realtime')
const loading = ref(false)
const result = ref(null)
const cameraActive = ref(false)
const recognized = ref(false)
const recognizedName = ref('')
const recogConfidence = ref(0)
const countdown = ref(0)
const countdownTotal = ref(3)
const livenessEnabled = ref(false)
const selectedSessionId = ref(null)
const sessions = ref([])
const challenge = reactive({ action: '', text: '' })
let cameraStream = null
let recogTimer = null
let lastRecognizeFile = null

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
  recogTimer = setInterval(() => {
    if (!cameraActive.value || mode.value !== 'realtime') return
    captureAndRecognize()
  }, 600)
}

function captureAndRecognize() {
  const video = videoRef.value; if (!video?.videoWidth) return
  const canvas = document.createElement('canvas')
  canvas.width = video.videoWidth; canvas.height = video.videoHeight
  canvas.getContext('2d').drawImage(video, 0, 0)
  canvas.toBlob(async (blob) => {
    if (!blob) return
    lastRecognizeFile = new File([blob], 'recog.jpg', { type: 'image/jpeg' })
    try {
      const { data } = await attendanceApi.recognize(lastRecognizeFile)
      drawFaceBoxes(data.faces)
      if (data.matched) {
        const mf = data.faces.find(f => f.matched && f.student)
        if (mf) {
          recognized.value = true
          recognizedName.value = mf.student.name
          recogConfidence.value = (mf.confidence * 100).toFixed(1)
        }
      } else {
        recognized.value = false
      }
    } catch { recognized.value = false }
  }, 'image/jpeg', 0.92)
}

function drawFaceBoxes(faces) {
  const canvas = overlayRef.value; const video = videoRef.value
  if (!canvas || !video?.videoWidth) return
  canvas.width = video.videoWidth; canvas.height = video.videoHeight
  const ctx = canvas.getContext('2d'); ctx.clearRect(0, 0, canvas.width, canvas.height)
  faces.forEach((f, i) => {
    const [x, y, w, h] = f.bbox; const color = f.matched ? '#10b981' : '#f59e0b'
    ctx.strokeStyle = color; ctx.lineWidth = 2; ctx.strokeRect(x, y, w, h)
    if (f.student) { ctx.fillStyle = color; ctx.font = '14px sans-serif'; ctx.fillText(f.student.name, x, y - 4) }
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
</style>
