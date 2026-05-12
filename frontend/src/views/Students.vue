<template>
  <div class="page">
    <div class="toolbar">
      <h2>学生管理</h2>
      <div>
        <el-input v-model="keyword" placeholder="姓名/学号" style="width: 180px; margin-right: 8px" clearable @clear="load" />
        <el-button :icon="Search" @click="load">查询</el-button>
        <input ref="batchInputRef" hidden type="file" accept="image/png,image/jpeg" multiple @change="batchChanged" />
        <el-button :icon="FolderAdd" @click="batchInputRef.click()">批量导入人脸</el-button>
        <el-button type="primary" :icon="Plus" @click="openCreate">新增学生</el-button>
      </div>
    </div>

    <el-table :data="paginatedRows" class="section" @row-click="openDetail" style="cursor: pointer">
      <el-table-column prop="student_no" label="学号" width="150" />
      <el-table-column prop="name" label="姓名" width="140" />
      <el-table-column prop="gender" label="性别" width="80" />
      <el-table-column prop="class_name" label="专业/班级" />
      <el-table-column label="人脸库" width="120">
        <template #default="{ row }">
          <el-tag :type="row.has_face ? 'success' : 'warning'" effect="plain" size="small">
            {{ row.has_face ? '已录入' : '未录入' }}
          </el-tag>
          <span v-if="row.face_sample_count > 1" style="font-size:11px;color:#9ca3af;margin-left:4px">
            {{ row.face_sample_count }}张
          </span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="280">
        <template #default="{ row }">
          <el-button size="small" :icon="CameraFilled" @click.stop="openFaceDialog(row)">录入人脸</el-button>
          <input ref="faceUploadInput" hidden type="file" accept="image/png,image/jpeg" @change="handleFileChange" />
          <el-button size="small" :icon="Edit" @click.stop="openEdit(row)">编辑</el-button>
          <el-button size="small" type="danger" :icon="Delete" @click.stop="remove(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <div v-if="rows.length > pageSize" class="pagination-wrapper">
      <el-pagination
        v-model:current-page="currentPage"
        :page-size="pageSize"
        :total="rows.length"
        layout="prev, pager, next"
        small
      />
    </div>

    <!-- 新增/编辑学生弹窗 -->
    <el-dialog v-model="visible" :title="form.id ? '编辑学生' : '新增学生'" width="420px" destroy-on-close>
      <el-form :model="form" label-width="70px">
        <el-form-item label="学号">
          <el-input v-model="form.student_no" placeholder="请输入学号" />
        </el-form-item>
        <el-form-item label="姓名">
          <el-input v-model="form.name" placeholder="请输入姓名" />
        </el-form-item>
        <el-form-item label="性别">
          <el-select v-model="form.gender" clearable placeholder="请选择">
            <el-option label="男" value="男" />
            <el-option label="女" value="女" />
          </el-select>
        </el-form-item>
        <el-form-item label="班级">
          <el-input v-model="form.class_name" placeholder="请输入班级" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="visible = false">取消</el-button>
        <el-button type="primary" :disabled="!form.student_no || !form.name" @click="save">保存</el-button>
      </template>
    </el-dialog>

    <!-- 批量导入结果 -->
    <el-dialog v-model="batchResultVisible" title="批量导入结果" width="620px">
      <el-descriptions :column="2" border>
        <el-descriptions-item label="成功">
          <span style="color:#10b981;font-weight:600">{{ batchResult.imported_count }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="失败">
          <span style="color:#ef4444;font-weight:600">{{ batchResult.failed_count }}</span>
        </el-descriptions-item>
      </el-descriptions>
      <el-table v-if="batchResult.failed.length" :data="batchResult.failed" style="margin-top: 14px">
        <el-table-column prop="filename" label="文件名" />
        <el-table-column prop="reason" label="失败原因" />
      </el-table>
    </el-dialog>

    <!-- 学生详情弹窗（查看照片） -->
    <el-dialog v-model="detailVisible" title="学生详情" width="520px" destroy-on-close>
      <div v-if="detailStudent" class="detail-wrap">
        <div class="detail-photo">
          <el-image
            v-if="detailStudent.face_image_url"
            :src="detailStudent.face_image_url"
            fit="cover"
            style="width: 200px; height: 240px; border-radius: 8px;"
          >
            <template #error>
              <div class="photo-placeholder">无照片</div>
            </template>
          </el-image>
          <div v-else class="photo-placeholder">无照片</div>
        </div>
        <el-descriptions :column="1" border style="flex:1">
          <el-descriptions-item label="学号" label-class-name="detail-label">
            {{ detailStudent.student_no }}
          </el-descriptions-item>
          <el-descriptions-item label="姓名">
            {{ detailStudent.name }}
          </el-descriptions-item>
          <el-descriptions-item label="性别">
            {{ detailStudent.gender || '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="专业/班级">
            {{ detailStudent.class_name }}
          </el-descriptions-item>
        </el-descriptions>
      </div>
    </el-dialog>

    <!-- 人脸录入弹窗（拍照 / 上传） -->
    <el-dialog v-model="faceDialog.visible" title="录入人脸" width="480px" :close-on-click-modal="false" @closed="closeFaceDialog">
      <!-- 模式选择 -->
      <div v-if="!faceDialog.method" class="face-method-select">
        <div class="face-method-card" @click="selectCamera">
          <el-icon :size="40"><CameraFilled /></el-icon>
          <span>拍照</span>
          <small>使用摄像头拍照录入</small>
        </div>
        <div class="face-method-card" @click="selectUpload">
          <el-icon :size="40"><UploadFilled /></el-icon>
          <span>上传照片</span>
          <small>从文件选择照片</small>
        </div>
      </div>

      <!-- 拍照模式 -->
      <div v-if="faceDialog.method === 'camera'" class="face-camera-wrap">
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
          <el-button @click="faceDialog.method = ''">返回</el-button>
          <el-button type="success" :icon="Check" :loading="faceDialog.loading" @click="captureAndSubmit">
            {{ faceDialog.loading ? '识别中...' : '拍照录入' }}
          </el-button>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  CameraFilled, Check, Delete, Edit, FolderAdd, Plus, Search, UploadFilled
} from '@element-plus/icons-vue'
import { studentApi } from '../api/modules'

const rows = ref([])
const keyword = ref('')
const visible = ref(false)
const batchInputRef = ref()
const faceUploadInput = ref()
const currentPage = ref(1)
const pageSize = ref(20)
const form = reactive({ id: null, student_no: '', name: '', class_name: '', gender: '' })
const batchResultVisible = ref(false)
const batchResult = reactive({ imported_count: 0, failed_count: 0, imported: [], failed: [] })
const detailVisible = ref(false)
const detailStudent = ref(null)
const videoRef = ref()

const faceDialog = reactive({
  visible: false,
  row: null,
  method: '',   // '' | 'camera' | 'upload'
  loading: false,
})
let cameraStream = null

const paginatedRows = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  return rows.value.slice(start, start + pageSize.value)
})

async function load() {
  currentPage.value = 1
  const { data } = await studentApi.list(keyword.value)
  rows.value = data
}

function openCreate() {
  Object.assign(form, { id: null, student_no: '', name: '', class_name: '', gender: '' })
  visible.value = true
}

function openEdit(row) {
  Object.assign(form, row)
  visible.value = true
}

async function save() {
  if (form.id) await studentApi.update(form.id, form)
  else await studentApi.create(form)
  visible.value = false
  await load()
}

async function remove(row) {
  await ElMessageBox.confirm(`确认删除 ${row.name}（${row.student_no}）？`, '删除确认')
  await studentApi.remove(row.id)
  await load()
}

// ---- 人脸录入 ----

function openFaceDialog(row) {
  faceDialog.row = row
  faceDialog.method = ''
  faceDialog.loading = false
  faceDialog.visible = true
}

function selectCamera() {
  faceDialog.method = 'camera'
  nextTick(startCamera)
}

function selectUpload() {
  faceDialog.method = 'upload'
  // 关闭弹窗后触发文件选择
  faceDialog.visible = false
  nextTick(() => faceUploadInput.value?.click())
}

async function startCamera() {
  try {
    cameraStream = await navigator.mediaDevices.getUserMedia({
      video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: 'user' },
      audio: false,
    })
    videoRef.value.srcObject = cameraStream
  } catch {
    ElMessage.error('摄像头启动失败，请检查浏览器权限')
    faceDialog.method = ''
  }
}

function captureAndSubmit() {
  const video = videoRef.value
  if (!video?.videoWidth) {
    ElMessage.warning('摄像头未就绪')
    return
  }
  faceDialog.loading = true
  const canvas = document.createElement('canvas')
  canvas.width = video.videoWidth
  canvas.height = video.videoHeight
  canvas.getContext('2d').drawImage(video, 0, 0)
  canvas.toBlob(async (blob) => {
    if (!blob) {
      faceDialog.loading = false
      ElMessage.error('拍照失败')
      return
    }
    const file = new File([blob], 'face-capture.jpg', { type: 'image/jpeg' })
    try {
      await studentApi.uploadFace(faceDialog.row.id, file)
      ElMessage.success('人脸录入成功')
      faceDialog.visible = false
      await load()
    } catch (e) {
      ElMessage.error(e.response?.data?.detail || '录入失败')
    } finally {
      faceDialog.loading = false
    }
  }, 'image/jpeg', 0.95)
}

function closeFaceDialog() {
  if (cameraStream) {
    cameraStream.getTracks().forEach((t) => t.stop())
    cameraStream = null
  }
  faceDialog.method = ''
  faceDialog.loading = false
}

function handleFileChange(event) {
  const file = event.target.files?.[0]
  if (!file) return
  const row = faceDialog.row
  if (!row) return
  studentApi.uploadFace(row.id, file).then(() => {
    ElMessage.success('人脸录入成功')
    load()
  }).catch((e) => {
    ElMessage.error(e.response?.data?.detail || '录入失败')
  })
  event.target.value = ''
}

// ---- 批量导入 ----

async function batchChanged(event) {
  const files = Array.from(event.target.files || [])
  if (!files.length) return
  try {
    const { data } = await studentApi.batchUploadFaces(files)
    Object.assign(batchResult, data)
    batchResultVisible.value = true
    ElMessage.success(`导入 ${data.imported_count} 张，失败 ${data.failed_count} 张`)
    await load()
  } finally {
    event.target.value = ''
  }
}

// ---- 详情 ----

function openDetail(row) {
  detailStudent.value = row
  detailVisible.value = true
}

onMounted(load)
</script>

<style scoped>
.pagination-wrapper {
  display: flex;
  justify-content: center;
  margin-top: 16px;
}

.detail-wrap {
  display: flex;
  gap: 24px;
  align-items: flex-start;
}

.detail-photo {
  flex-shrink: 0;
  width: 200px;
  height: 240px;
}

.photo-placeholder {
  width: 200px;
  height: 240px;
  border-radius: 8px;
  background: #f3f4f6;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #9ca3af;
  font-size: 14px;
}

/* 人脸录入弹窗 */
.face-method-select {
  display: flex;
  gap: 16px;
  justify-content: center;
  padding: 20px 0;
}

.face-method-card {
  width: 160px;
  padding: 28px 16px;
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

/* 拍照区域 */
.face-camera-wrap {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.camera-wrapper {
  position: relative;
  width: 100%;
  aspect-ratio: 4 / 3;
  border-radius: 8px;
  overflow: hidden;
  background: #111827;
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
</style>
