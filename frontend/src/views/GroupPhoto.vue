<template>
  <div class="page">
    <div class="toolbar">
      <h2>合照识别</h2>
      <el-select v-model="selectedSessionId" placeholder="选择考勤活动" style="width:220px;margin-right:8px" clearable>
        <el-option v-for="s in sessions" :key="s.id" :label="`${s.course_name} ${s.date}`" :value="s.id" />
      </el-select>
    </div>
    <div class="section">
      <div class="upload-area">
        <input ref="fileInput" hidden type="file" accept="image/png,image/jpeg" @change="handleFile" />
        <div v-if="!previewUrl" class="drop-zone" @click="fileInput.click()" @drop.prevent="handleDrop" @dragover.prevent>
          <el-icon size="42"><UploadFilled /></el-icon><div class="upload-text">拖拽或点击上传合照</div><div class="upload-hint">JPG/PNG，小于 1000MB</div>
        </div>
        <div v-else class="preview-wrapper">
          <img :src="annotatedUrl || previewUrl" class="preview-img" />
          <div class="preview-actions">
            <el-button size="small" @click="clearPreview">重新选择</el-button>
            <el-button size="small" type="primary" :loading="recognizing" @click="startRecognize">开始识别</el-button>
          </div>
        </div>
      </div>
      <div v-if="results.length" class="result-section">
        <div class="summary-bar">检测 {{ faceCount }} 张人脸，识别 {{ recognizedCount }} 人，未识别 {{ unmatchedCount }} 人</div>
        <el-table :data="results" stripe>
          <el-table-column prop="no" label="#" width="50" />
          <el-table-column label="学号" width="150"><template #default="{row}">{{ row.student?.student_no || '—' }}</template></el-table-column>
          <el-table-column label="姓名" width="100"><template #default="{row}">{{ row.student?.name || '—' }}</template></el-table-column>
          <el-table-column label="班级"><template #default="{row}">{{ row.student?.class_name || '—' }}</template></el-table-column>
          <el-table-column label="置信度" width="100"><template #default="{row}">{{ row.matched ? (row.confidence*100).toFixed(1)+'%' : '—' }}</template></el-table-column>
          <el-table-column label="操作" width="200">
            <template #default="{row}">
              <template v-if="!row.student">
                <el-input v-model="manualSearch[row.no]" placeholder="学号/姓名" size="small" style="width:120px" @change="searchStudent(row.no)" />
              </template>
              <template v-else>✅ 已匹配</template>
            </template>
          </el-table-column>
        </el-table>
        <div style="margin-top:12px"><el-button type="primary" :disabled="!selectedSessionId" @click="saveAll">保存全部</el-button></div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { UploadFilled } from '@element-plus/icons-vue'
import { groupPhotoApi, sessionApi, studentApi } from '../api/modules'

const fileInput = ref(null)
const previewUrl = ref(null)
const annotatedUrl = ref(null)
const recognizing = ref(false)
const selectedSessionId = ref(null)
const sessions = ref([])
const results = ref([])
const faceCount = ref(0)
const recognizedCount = ref(0)
const unmatchedCount = ref(0)
const manualSearch = reactive({})
let currentFile = null

async function loadSessions() { try { const { data } = await sessionApi.listActive(); sessions.value = data } catch {} }

function handleFile(e) { const f = e.target?.files?.[0]; if (!f) return; setFile(f); e.target.value = '' }
function handleDrop(e) { const f = e.dataTransfer?.files?.[0]; if (!f?.type?.startsWith('image/')) return; setFile(f) }
function setFile(f) { currentFile = f; previewUrl.value = URL.createObjectURL(f); annotatedUrl.value = null; results.value = [] }
function clearPreview() { if (previewUrl.value) URL.revokeObjectURL(previewUrl.value); previewUrl.value = null; currentFile = null }

async function startRecognize() {
  if (!currentFile) return; recognizing.value = true
  try {
    const { data } = await groupPhotoApi.recognize(currentFile, '合照活动')
    annotatedUrl.value = '/' + data.annotated_image
    faceCount.value = data.face_count
    recognizedCount.value = data.recognized.filter(r => r.matched).length
    unmatchedCount.value = data.unmatched_count
    results.value = data.recognized
  } finally { recognizing.value = false }
}

async function searchStudent(rowNo) {
  const kw = manualSearch[rowNo]; if (!kw) return
  const { data } = await studentApi.list(kw)
  if (data.length === 1) {
    const s = data[0]
    const row = results.value.find(r => r.no === rowNo)
    if (row) { row.student = { id: s.id, student_no: s.student_no, name: s.name, class_name: s.class_name }; row.matched = true; row.confidence = 1.0 }
  } else if (data.length > 1) { ElMessage.warning('找到多个结果，请细化搜索') } else { ElMessage.warning('未找到匹配学生') }
}

async function saveAll() {
  if (!selectedSessionId.value) { ElMessage.warning('请选择考勤活动'); return }
  const records = results.value.filter(r => r.student).map(r => ({
    no: r.no, student_id: r.student.id, confidence: r.confidence || 0, emotion: r.emotion || null
  }))
  const { data } = await groupPhotoApi.save({ session_id: selectedSessionId.value, records })
  ElMessage.success(`已保存 ${data.saved_count} 条记录`)
}

onMounted(loadSessions)
</script>

<style scoped>
.upload-area { display: flex; justify-content: center }
.drop-zone { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 8px; width: 100%; max-width: 420px; min-height: 160px; border: 2px dashed #d9d9d9; border-radius: 8px; background: #fafafa; cursor: pointer; transition: all 0.2s; padding: 20px; color: #909399 }
.drop-zone:hover { border-color: #409eff; color: #409eff; background: #ecf5ff }
.upload-text { margin-top: 8px; font-size: 15px; color: #374151 }
.upload-hint { margin-top: 4px; font-size: 12px; color: #9ca3af }
.preview-wrapper { display: flex; flex-direction: column; align-items: center; gap: 12px }
.preview-img { max-width: 100%; max-height: 400px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1) }
.preview-actions { display: flex; gap: 8px }
.result-section { margin-top: 16px }
.summary-bar { padding: 8px 16px; background: #f0f9ff; border: 1px solid #bfdbfe; border-radius: 8px; margin-bottom: 12px; font-size: 14px; color: #1e40af }
</style>
