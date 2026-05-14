<template>
  <div class="page">
    <div class="toolbar">
      <h2>我的信息</h2>
    </div>

    <el-card v-if="student" class="section">
      <el-descriptions :column="2" border>
        <el-descriptions-item label="学号">{{ student.student_no }}</el-descriptions-item>
        <el-descriptions-item label="姓名">{{ student.name }}</el-descriptions-item>
        <el-descriptions-item label="班级">{{ student.class_name }}</el-descriptions-item>
        <el-descriptions-item label="性别">{{ student.gender || '-' }}</el-descriptions-item>
        <el-descriptions-item label="人脸状态">
          <el-tag :type="student.has_face ? 'success' : 'warning'" effect="plain" size="small">
            {{ student.has_face ? '已录入' : '未录入' }}
          </el-tag>
        </el-descriptions-item>
      </el-descriptions>
    </el-card>

    <el-card class="section face-card" style="margin-top: 16px">
      <template #header>
        <div class="card-header">
          <span>我的人脸</span>
          <el-button
            v-if="student?.face_image_url"
            link
            type="primary"
            :icon="View"
            @click="openFacePreview"
          >
            查看当前照片
          </el-button>
        </div>
      </template>
      <div class="current-face">
        <button
          v-if="student?.face_image_url"
          class="current-face-photo"
          type="button"
          @click="openFacePreview"
        >
          <img :src="student.face_image_url" alt="当前人脸照片" />
          <span>点击查看数据库中的当前照片</span>
        </button>
        <div v-else class="current-face-empty">暂无已录入的人脸照片</div>
      </div>

      <!-- 模式选择 -->
      <div v-if="!method" class="face-method-select">
        <div class="face-method-card" @click="startCamera">
          <el-icon :size="40"><CameraFilled /></el-icon>
          <span>拍照录入</span>
          <small>使用摄像头拍照</small>
        </div>
        <div class="face-method-card" @click="triggerUpload">
          <el-icon :size="40"><UploadFilled /></el-icon>
          <span>上传照片</span>
          <small>从文件选择照片</small>
        </div>
      </div>

      <!-- 拍照模式 -->
      <div v-if="method === 'camera'" class="face-camera-wrap">
        <div class="camera-wrapper">
          <video ref="videoRef" class="camera-video" autoplay muted playsinline />
          <div class="camera-guide">
            <svg viewBox="0 0 200 260" class="guide-svg">
              <ellipse cx="100" cy="130" rx="75" ry="95" fill="none"
                stroke="rgba(255,255,255,0.4)" stroke-width="2.5" stroke-dasharray="6 4" />
            </svg>
            <span class="guide-text">请将面部对准椭圆区域</span>
          </div>
        </div>
        <div class="face-camera-actions">
          <el-button @click="closeCamera">返回</el-button>
          <el-button type="success" :icon="Check" :loading="loading" @click="captureAndUpload">
            {{ loading ? '识别中...' : '拍照上传' }}
          </el-button>
        </div>
      </div>

      <div v-else-if="method === 'done'" class="face-result">
        <el-result icon="success" title="上传成功" sub-title="人脸照片已录入">
          <template #extra>
            <el-button type="primary" @click="method = ''">继续录入</el-button>
          </template>
        </el-result>
      </div>
    </el-card>

    <el-card class="section account-card" style="margin-top: 16px">
      <template #header>
        <div class="card-header">
          <span>我的账户</span>
        </div>
      </template>
      <el-form class="account-form" :model="passwordForm" label-width="86px">
        <el-form-item label="原密码">
          <el-input v-model="passwordForm.old_password" type="password" show-password autocomplete="current-password" />
        </el-form-item>
        <el-form-item label="新密码">
          <el-input v-model="passwordForm.new_password" type="password" show-password autocomplete="new-password" />
        </el-form-item>
        <el-form-item label="确认密码">
          <el-input v-model="passwordForm.confirm_password" type="password" show-password autocomplete="new-password" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :icon="Lock" :loading="passwordLoading" @click="submitPassword">
            修改密码
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-dialog v-model="facePreviewVisible" title="当前人脸照片" width="480px" destroy-on-close>
      <img v-if="student?.face_image_url" :src="student.face_image_url" class="face-preview-image" alt="当前人脸照片" />
    </el-dialog>

    <input ref="fileInputRef" hidden type="file" accept="image/png,image/jpeg" @change="onFileChange" />
  </div>
</template>

<script setup>
import { nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { CameraFilled, Check, Lock, UploadFilled, View } from '@element-plus/icons-vue'
import { authApi, studentApi } from '../api/modules'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const student = ref(null)
const method = ref('')  // '' | 'camera' | 'done'
const loading = ref(false)
const passwordLoading = ref(false)
const facePreviewVisible = ref(false)
const videoRef = ref()
const fileInputRef = ref()
const passwordForm = reactive({
  old_password: '',
  new_password: '',
  confirm_password: '',
})
let cameraStream = null

async function loadMyInfo() {
  try {
    const { data } = await studentApi.getMe()
    student.value = data
  } catch {
    ElMessage.error('获取学生信息失败')
  }
}

function triggerUpload() {
  fileInputRef.value?.click()
}

function openFacePreview() {
  if (!student.value?.face_image_url) {
    ElMessage.warning('当前还没有数据库照片')
    return
  }
  facePreviewVisible.value = true
}

async function onFileChange(event) {
  const file = event.target.files?.[0]
  if (!file) return
  await uploadFace(file)
  event.target.value = ''
}

async function startCamera() {
  method.value = 'camera'
  await nextTick()
  try {
    cameraStream = await navigator.mediaDevices.getUserMedia({
      video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: 'user' },
      audio: false,
    })
    if (videoRef.value) {
      videoRef.value.srcObject = cameraStream
    }
  } catch {
    ElMessage.error('摄像头启动失败，请检查浏览器权限')
    method.value = ''
  }
}

function closeCamera() {
  if (cameraStream) {
    cameraStream.getTracks().forEach((t) => t.stop())
    cameraStream = null
  }
  method.value = ''
}

function captureAndUpload() {
  const video = videoRef.value
  if (!video?.videoWidth) {
    ElMessage.warning('摄像头未就绪')
    return
  }
  loading.value = true
  const canvas = document.createElement('canvas')
  canvas.width = video.videoWidth
  canvas.height = video.videoHeight
  canvas.getContext('2d').drawImage(video, 0, 0)
  canvas.toBlob(async (blob) => {
    if (!blob) {
      loading.value = false
      ElMessage.error('拍照失败')
      return
    }
    await uploadFace(new File([blob], 'face-capture.jpg', { type: 'image/jpeg' }))
  }, 'image/jpeg', 0.95)
}

async function uploadFace(file) {
  loading.value = true
  try {
    await studentApi.uploadMyFace(file)
    ElMessage.success('人脸录入成功')
    method.value = 'done'
    await loadMyInfo()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '录入失败')
  } finally {
    loading.value = false
  }
}

async function submitPassword() {
  if (!passwordForm.old_password || !passwordForm.new_password || !passwordForm.confirm_password) {
    ElMessage.warning('请完整填写密码信息')
    return
  }
  if (passwordForm.new_password.length < 6) {
    ElMessage.warning('新密码至少 6 位')
    return
  }
  if (passwordForm.new_password !== passwordForm.confirm_password) {
    ElMessage.warning('两次输入的新密码不一致')
    return
  }
  passwordLoading.value = true
  try {
    await authApi.changePassword({
      old_password: passwordForm.old_password,
      new_password: passwordForm.new_password,
    })
    Object.assign(passwordForm, { old_password: '', new_password: '', confirm_password: '' })
    ElMessage.success('密码修改成功')
  } finally {
    passwordLoading.value = false
  }
}

onMounted(() => {
  if (auth.role === 'student') loadMyInfo()
})

onBeforeUnmount(() => {
  if (cameraStream) {
    cameraStream.getTracks().forEach((t) => t.stop())
    cameraStream = null
  }
})
</script>

<style scoped>
.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.current-face {
  margin-bottom: 14px;
}

.current-face-photo {
  width: 100%;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #f8fafc;
  padding: 12px;
  display: flex;
  align-items: center;
  gap: 14px;
  cursor: pointer;
  color: #374151;
  text-align: left;
  transition: all 0.2s ease;
}

.current-face-photo:hover {
  border-color: #409eff;
  background: #ecf5ff;
  color: #2563eb;
}

.current-face-photo img {
  width: 72px;
  height: 88px;
  border-radius: 6px;
  object-fit: cover;
  background: #e5e7eb;
}

.current-face-photo span {
  font-size: 14px;
  font-weight: 500;
}

.current-face-empty {
  border: 1px dashed #d1d5db;
  border-radius: 8px;
  padding: 18px;
  color: #9ca3af;
  text-align: center;
  background: #f9fafb;
}

.account-form {
  max-width: 420px;
}

.face-preview-image {
  width: 100%;
  max-height: 68vh;
  display: block;
  border-radius: 8px;
  object-fit: contain;
  background: #111827;
}

.face-method-select {
  display: flex;
  gap: 16px;
  justify-content: center;
  padding: 20px 0;
}

.face-method-card {
  width: 180px;
  padding: 32px 20px;
  border: 2px solid #e5e7eb;
  border-radius: 12px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  transition: all 0.2s;
  color: #374151;
}
.face-method-card:hover {
  border-color: #409eff;
  color: #409eff;
  background: #ecf5ff;
}
.face-method-card span {
  font-size: 16px;
  font-weight: 600;
}
.face-method-card small {
  font-size: 12px;
  color: #9ca3af;
}

.face-camera-wrap {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.camera-wrapper {
  position: relative;
  width: 100%;
  max-width: 500px;
  aspect-ratio: 4 / 3;
  border-radius: 8px;
  overflow: hidden;
  background: #111827;
  margin: 0 auto;
}

.camera-video {
  width: 100%;
  height: 100%;
  display: block;
  object-fit: cover;
}

.camera-guide {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  pointer-events: none;
}

.guide-svg {
  width: 160px;
  height: 210px;
}

.guide-text {
  position: absolute;
  bottom: 12%;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.6);
  background: rgba(0, 0, 0, 0.5);
  padding: 4px 14px;
  border-radius: 20px;
  white-space: nowrap;
}

.face-camera-actions {
  display: flex;
  justify-content: center;
  gap: 12px;
}

.face-result {
  padding: 20px 0;
}
</style>
