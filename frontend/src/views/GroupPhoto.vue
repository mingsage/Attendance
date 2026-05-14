<template>
  <div class="page">
    <div class="toolbar">
      <h2>合照识别</h2>
      <el-input v-model="activityName" style="width: 240px" placeholder="活动名称" clearable />
    </div>
    <div class="section">
      <div class="upload-area">
        <input ref="fileInputRef" hidden type="file" accept="image/png,image/jpeg" @change="handleFileSelect" />
        <div v-if="!previewUrl" class="drop-zone" @click="fileInputRef.click()" @drop.prevent="handleDrop" @dragover.prevent>
          <el-icon size="42"><UploadFilled /></el-icon>
          <div class="upload-text">拖拽或点击上传班级合照</div>
          <div class="upload-hint">支持 JPG / PNG 格式</div>
        </div>
        <div v-else class="preview-wrapper">
          <img :src="previewUrl" class="preview-img" alt="合照预览" />
          <div class="preview-actions">
            <el-button size="small" @click="clearPreview">重新选择</el-button>
            <el-button size="small" type="primary" :loading="recognizing" @click="startRecognize">开始识别</el-button>
          </div>
        </div>
      </div>

      <!-- 识别结果摘要 -->
      <transition name="fade">
        <div v-if="summary" class="result-summary">
          <div class="summary-card">
            <div class="summary-stat">
              <span class="summary-value">{{ summary.face_count }}</span>
              <span class="summary-label">检测到人脸</span>
            </div>
            <div class="summary-divider" />
            <div class="summary-stat">
              <span class="summary-value" style="color:#10b981">{{ summary.recognized_count }}</span>
              <span class="summary-label">成功识别</span>
            </div>
            <div class="summary-divider" />
            <div class="summary-stat">
              <span class="summary-value" :style="{ color: summary.face_count - summary.recognized_count > 0 ? '#ef4444' : '#10b981' }">
                {{ summary.face_count - summary.recognized_count }}
              </span>
              <span class="summary-label">未识别</span>
            </div>
          </div>
        </div>
      </transition>

      <!-- 识别结果表格 -->
      <transition name="fade">
        <el-table v-if="results.length" :data="results" style="margin-top: 16px">
          <el-table-column type="index" label="#" width="50" />
          <el-table-column prop="student_no" label="学号" width="150">
            <template #default="{ row }">
              <span class="student-link" @click="showDetail(row)">{{ row.student_no }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="name" label="姓名" width="120">
            <template #default="{ row }">
              <span class="student-link" @click="showDetail(row)">{{ row.name }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="class_name" label="班级" />
          <el-table-column label="置信度" width="120">
            <template #default="{ row }">
              <el-progress
                :percentage="Math.round((row.confidence || 0) * 100)"
                :stroke-width="14"
                :status="row.confidence >= 0.68 ? 'success' : 'warning'"
                :format="() => (row.confidence * 100).toFixed(1) + '%'"
              />
            </template>
          </el-table-column>
          <el-table-column label="情绪" width="130">
            <template #default="{ row }">
              <span style="white-space: nowrap">{{ EMOTION_MAP[row.emotion] || row.emotion }}</span>
            </template>
          </el-table-column>
        </el-table>
      </transition>
    </div>
    <StudentDetail v-model:visible="detailVisible" :student-id="detailStudentId" />
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { groupPhotoApi } from '../api/modules'
import StudentDetail from '../components/StudentDetail.vue'

const EMOTION_MAP = {
  happy: '😊 Happy',
  sad: '😢 Sad',
  angry: '😠 Angry',
  surprised: '😮 Surprised',
  fearful: '😨 Fearful',
  disgusted: '🤢 Disgusted',
  neutral: '😐 Neutral',
}

const detailVisible = ref(false)
const detailStudentId = ref(null)

function showDetail(row) {
  if (row.student_id) {
    detailStudentId.value = row.student_id
    detailVisible.value = true
  }
}

const fileInputRef = ref()
const activityName = ref('班级活动')
const summary = ref(null)
const results = ref([])
const previewUrl = ref(null)
const recognizing = ref(false)
let currentFile = null

function handleFileSelect(e) {
  const file = e.target?.files?.[0]
  if (!file) return
  currentFile = file
  previewUrl.value = URL.createObjectURL(file)
  summary.value = null
  results.value = []
  e.target.value = ''
}

function handleDrop(e) {
  const file = e.dataTransfer?.files?.[0]
  if (!file || !file.type.startsWith('image/')) return
  currentFile = file
  previewUrl.value = URL.createObjectURL(file)
  summary.value = null
  results.value = []
}

function clearPreview() {
  if (previewUrl.value) URL.revokeObjectURL(previewUrl.value)
  previewUrl.value = null
  currentFile = null
}

async function startRecognize() {
  if (!currentFile) return
  recognizing.value = true
  try {
    const { data } = await groupPhotoApi.recognize(currentFile, activityName.value)
    summary.value = data
    results.value = data.results
    ElMessage.success(`识别完成：${data.recognized_count} 人`)
  } finally {
    recognizing.value = false
  }
}
</script>

<style scoped>
.upload-area {
  display: flex;
  justify-content: center;
}

.drop-zone {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  width: 100%;
  max-width: 420px;
  min-height: 160px;
  border: 2px dashed #d9d9d9;
  border-radius: 8px;
  background: #fafafa;
  cursor: pointer;
  transition: all 0.2s;
  padding: 20px;
  color: #909399;
}
.drop-zone:hover {
  border-color: #409eff;
  color: #409eff;
  background: #ecf5ff;
}

.upload-text {
  margin-top: 8px;
  font-size: 15px;
  color: #374151;
}

.upload-hint {
  margin-top: 4px;
  font-size: 12px;
  color: #9ca3af;
}

.preview-wrapper {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}

.preview-img {
  max-width: 100%;
  max-height: 400px;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.preview-actions {
  display: flex;
  gap: 8px;
}

.result-summary {
  margin-top: 16px;
  animation: fadeIn 0.3s ease;
}

.summary-card {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0;
  background: #f8fafc;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 16px 24px;
}

.summary-stat {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 0 24px;
}

.summary-value {
  font-size: 28px;
  font-weight: 700;
  color: #2563eb;
}

.summary-label {
  font-size: 13px;
  color: #6b7280;
  margin-top: 2px;
}

.summary-divider {
  width: 1px;
  height: 40px;
  background: #e5e7eb;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}

</style>
