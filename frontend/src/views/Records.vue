<template>
  <div class="page">
    <div class="toolbar">
      <h2>考勤记录</h2>
      <div class="toolbar-group">
        <el-select v-model="courseName" placeholder="选择课程" clearable style="width: 160px" @clear="onCourseClear" @change="onCourseChange">
          <el-option v-for="name in courseList" :key="name" :label="name" :value="name" />
        </el-select>
        <el-select v-model="selectedDate" placeholder="选择日期" clearable :disabled="!courseName" style="width: 140px" @clear="load" @change="load">
          <el-option v-for="d in dateList" :key="d" :label="d" :value="d" />
        </el-select>
        <el-input v-model="keyword" placeholder="姓名/学号" style="width: 150px" clearable @clear="load" />
        <el-select v-model="status" placeholder="状态" style="width: 110px" clearable @change="load">
          <el-option label="成功" value="success" />
          <el-option label="失败" value="failed" />
        </el-select>
        <el-button :icon="Search" @click="load">查询</el-button>
        <el-button v-if="auth.role === 'teacher'" type="danger" :icon="Delete" :disabled="!selectedRows.length" @click="batchDeleteRecords">
          批量删除 ({{ selectedRows.length }})
        </el-button>
        <el-dropdown trigger="click" @command="handleExport">
          <el-button type="primary" :icon="Download">
            导出
          </el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="records">导出考勤明细</el-dropdown-item>
              <el-dropdown-item command="stats" :disabled="!courseName">导出统计报表</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </div>

    <!-- 统计概览 -->
    <div v-if="showStats" class="summary section" style="margin-bottom: 12px; animation: fadeIn 0.3s ease">
      <div class="compact-grid">
        <div class="metric" style="padding:14px 20px">
          <div class="label">应到</div>
          <div class="value" style="font-size:22px">{{ totalCount }}</div>
        </div>
        <div class="metric" style="padding:14px 20px">
          <div class="label">实到</div>
          <div class="value" style="font-size:22px;color:#059669">{{ signedCount }}</div>
        </div>
        <div class="metric" style="padding:14px 20px">
          <div class="label">缺勤</div>
          <div class="value" style="font-size:22px;color:#dc2626">{{ absentCount }}</div>
        </div>
        <div class="metric" style="padding:14px 20px;background:#eff6ff;border-color:#bfdbfe">
          <div class="label">到课率</div>
          <div class="value" style="font-size:22px;color:#2563eb">{{ attendanceRate }}%</div>
        </div>
      </div>
      <div v-if="absentList.length" class="absent-list">
        <span class="absent-label">未签到学生：</span>
        <el-tag v-for="s in absentList" :key="s.student_no" type="danger" size="small" effect="plain" style="margin: 2px 4px 2px 0">
          {{ s.name }}（{{ s.student_no }}）
        </el-tag>
      </div>
    </div>

    <!-- 考勤明细表 -->
    <el-table ref="tableRef" :data="rows" class="section" stripe border @sort-change="onSort" @row-click="showDetailFromRow" @selection-change="onSelectionChange" style="cursor: pointer">
      <el-table-column type="expand" width="40">
        <template #default="{ row }">
          <div v-if="row.activities?.length" class="expand-activities">
            <div class="expand-title">参与活动</div>
            <div v-for="act in row.activities" :key="act.activity_name + act.activity_date" class="expand-item">
              <span class="expand-act-name">{{ act.activity_name }}</span>
              <span class="expand-act-date">{{ act.activity_date }}</span>
              <span class="expand-act-conf">置信度 {{ (act.confidence * 100).toFixed(1) }}%</span>
            </div>
          </div>
          <div v-else class="expand-empty">暂无活动参与记录</div>
        </template>
      </el-table-column>
      <el-table-column type="selection" width="40" />
      <el-table-column prop="timestamp" label="时间" width="170" sortable="custom">
        <template #default="{ row }">{{ formatTime(row.timestamp) }}</template>
      </el-table-column>
      <el-table-column label="课程" min-width="160">
        <template #default="{ row }">
          {{ row.course_name }}
          <span v-if="row.session_num" style="font-size:11px;color:#9ca3af">
            · 课次{{ row.session_num }} ({{ formatSessionDate(row.timestamp) }})
            <template v-if="row.session_count"> · {{ row.session_count }}人</template>
          </span>
        </template>
      </el-table-column>
      <el-table-column label="学生" width="300">
        <template #default="{ row }">
          <span v-if="row.student" class="student-link">
            <span style="font-weight: 500">{{ row.student.name }}</span>
            <span style="color: #9ca3af; font-size: 12px; margin-left: 6px">{{ row.student.student_no }}</span>
          </span>
          <span v-else style="color: #9ca3af">-</span>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <span :class="['status-tag', row.status]" style="white-space: nowrap">
            {{ row.status === 'success' ? '成功' : '失败' }}
          </span>
        </template>
      </el-table-column>
      <el-table-column prop="confidence" label="置信度" width="115" sortable="custom" align="center">
        <template #default="{ row }">
          <span v-if="row.confidence !== null" :style="{ color: row.confidence >= 0.58 ? 'var(--success)' : 'var(--danger)', fontWeight: 600 }">
            {{ (row.confidence * 100).toFixed(1) }}%
          </span>
          <span v-else style="color: #9ca3af">-</span>
        </template>
      </el-table-column>
      <el-table-column label="活体分" width="85" align="center">
        <template #default="{ row }">
          <span v-if="row.liveness_score" :style="{ color: row.liveness_score >= 0.3 ? 'var(--success)' : 'var(--danger)' }">
            {{ row.liveness_score.toFixed(2) }}
          </span>
          <span v-else style="color: #9ca3af">-</span>
        </template>
      </el-table-column>
      <el-table-column label="情绪" width="140">
        <template #default="{ row }">
          <span v-if="row.emotion_type" style="white-space: nowrap">{{ EMOTION_MAP[row.emotion_type] || row.emotion_type }}</span>
          <span v-else style="color: #9ca3af">-</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="70" fixed="right">
        <template #default="{ row }">
          <el-button v-if="auth.role === 'teacher'" type="danger" size="small" :icon="Delete" circle @click.stop="deleteRecord(row)" />
        </template>
      </el-table-column>
    </el-table>

    <!-- 签到照片弹窗 -->
    <el-dialog v-model="photoVisible" title="签到照片" width="420px" destroy-on-close>
      <div v-if="photoUrl" class="photo-preview">
        <img :src="photoUrl" style="width: 100%; border-radius: 8px; display: block" />
        <div class="photo-info">
          <p><strong>时间：</strong>{{ formatTime(photoRecord?.timestamp) }}</p>
          <p><strong>状态：</strong>
            <span :class="['status-tag', photoRecord?.status]">
              {{ photoRecord?.status === 'success' ? '成功' : '失败' }}
            </span>
          </p>
          <p v-if="photoRecord?.course_name"><strong>课程：</strong>{{ photoRecord.course_name }}</p>
          <p v-if="photoRecord?.message"><strong>备注：</strong>{{ photoRecord.message }}</p>
        </div>
      </div>
      <div v-else style="text-align: center; color: #999; padding: 40px">
        暂无签到照片
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Delete, Download, Search } from '@element-plus/icons-vue'
import { attendanceApi, statisticsApi } from '../api/modules'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()

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

const rows = ref([])
const keyword = ref('')
const status = ref('')
const photoVisible = ref(false)
const photoUrl = ref('')
const photoRecord = ref(null)
const selectedRows = ref([])
const tableRef = ref(null)

// 统计相关
const courseName = ref('')
const selectedDate = ref('')
const courseList = ref([])
const dateList = ref([])
const statsRows = ref([])

const showStats = computed(() => courseName.value && selectedDate.value)
const signedList = computed(() => statsRows.value.filter((r) => r.count))
const absentList = computed(() => statsRows.value.filter((r) => !r.count))
const totalCount = computed(() => statsRows.value.length)
const signedCount = computed(() => signedList.value.length)
const absentCount = computed(() => absentList.value.length)
const attendanceRate = computed(() => {
  if (!statsRows.value.length) return 0
  return ((signedCount.value / statsRows.value.length) * 100).toFixed(1)
})

function onSelectionChange(selection) {
  selectedRows.value = selection
}

function formatTime(ts) {
  if (!ts) return '-'
  const d = new Date(ts)
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

function formatSessionDate(ts) {
  if (!ts) return ''
  const d = new Date(ts)
  return `${d.getMonth() + 1}月${d.getDate()}日`
}

function onSort({ prop, order }) {
  if (!prop || !order) return
  rows.value.sort((a, b) => {
    const va = a[prop] ?? 0
    const vb = b[prop] ?? 0
    return order === 'ascending' ? va - vb : vb - va
  })
}

async function load() {
  const params = { keyword: keyword.value, status: status.value, limit: 500 }
  if (courseName.value) params.course_name = courseName.value
  const { data } = await attendanceApi.records(params)
  rows.value = data

  if (courseName.value && selectedDate.value) {
    const { data: stats } = await statisticsApi.attendanceStats(courseName.value, selectedDate.value)
    statsRows.value = stats
  } else {
    statsRows.value = []
  }
}

function showDetailFromRow(row) {
  photoUrl.value = row.photo_url || ''
  photoRecord.value = row
  photoVisible.value = true
}

async function deleteRecord(row) {
  try {
    await ElMessageBox.confirm(`确定删除 ${row.student?.name || '该'} 考勤记录吗？` + (
      row.photo_url ? '\n\n签到照片也会一并删除。' : ''
    ), '确认删除', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
    })
  } catch {
    return
  }
  await attendanceApi.deleteRecord(row.id)
  ElMessage.success('已删除')
  await load()
}

async function batchDeleteRecords() {
  const ids = selectedRows.value.map((r) => r.id)
  if (!ids.length) return
  try {
    await ElMessageBox.confirm(
      `确定删除选中的 ${ids.length} 条考勤记录吗？\n\n关联的签到照片也会一并删除。`,
      '批量删除',
      { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' },
    )
  } catch {
    return
  }
  await attendanceApi.batchDeleteRecords(ids)
  ElMessage.success(`已删除 ${ids.length} 条记录`)
  selectedRows.value = []
  await load()
}

async function handleExport(command) {
  if (command === 'records') await exportRecords()
  else if (command === 'stats') await exportStats()
}

async function exportRecords() {
  const params = { keyword: keyword.value, status: status.value }
  if (courseName.value) params.course_name = courseName.value
  const { data } = await attendanceApi.export(params)
  const url = URL.createObjectURL(data)
  const a = document.createElement('a')
  a.href = url
  a.download = 'attendance.xlsx'
  a.click()
  URL.revokeObjectURL(url)
}

async function exportStats() {
  if (!courseName.value) return
  const { data } = await statisticsApi.attendanceExport(courseName.value)
  const url = URL.createObjectURL(data)
  const a = document.createElement('a')
  a.href = url
  a.download = `${courseName.value}-考勤统计.xlsx`
  a.click()
  URL.revokeObjectURL(url)
}

async function loadCourses() {
  const { data } = await statisticsApi.courseList()
  courseList.value = data
}

async function onCourseChange(name) {
  selectedDate.value = ''
  if (name) {
    const { data } = await statisticsApi.courseDates(name)
    dateList.value = data
  } else {
    dateList.value = []
  }
  load()
}

function onCourseClear() {
  selectedDate.value = ''
  dateList.value = []
  load()
}

onMounted(() => {
  loadCourses()
  load()
})
</script>

<style scoped>
.toolbar-group {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
}

.summary {
  margin-bottom: 16px;
}

.compact-grid {
  display: flex;
  gap: 12px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}

.compact-grid .metric {
  min-width: 100px;
  flex: 1;
}

.absent-list {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 2px;
  padding: 8px 12px;
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 8px;
}

.expand-activities {
  padding: 8px 16px;
}

.expand-title {
  font-size: 14px;
  font-weight: 600;
  color: #374151;
  margin-bottom: 8px;
}

.expand-item {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 6px 12px;
  background: #f8fafc;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  margin-bottom: 4px;
}

.expand-item:last-child {
  margin-bottom: 0;
}

.expand-act-name {
  font-weight: 500;
  color: #2563eb;
}

.expand-act-date {
  font-size: 12px;
  color: #6b7280;
}

.expand-act-conf {
  font-size: 12px;
  color: #9ca3af;
  margin-left: auto;
}

.expand-empty {
  padding: 12px 16px;
  color: #9ca3af;
  font-size: 13px;
}

.absent-label {
  font-size: 13px;
  font-weight: 500;
  color: #991b1b;
  margin-right: 4px;
}

</style>
