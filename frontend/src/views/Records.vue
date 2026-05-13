<template>
  <div class="page">
    <div class="toolbar">
      <h2>考勤记录</h2>
      <div>
        <el-input v-model="filters.keyword" placeholder="姓名/学号" style="width: 180px; margin-right: 8px" clearable @clear="load" />
        <el-select v-model="filters.status" placeholder="状态" style="width: 130px; margin-right: 8px" clearable @change="load">
          <el-option label="成功" value="success" />
          <el-option label="失败" value="failed" />
        </el-select>
        <el-button :icon="Search" @click="load">查询</el-button>
        <el-button type="primary" :icon="Download" @click="download">导出</el-button>
      </div>
    </div>
    <el-table :data="paginatedRows" class="section" stripe border @sort-change="onSort" @row-click="showDetailFromRow" style="cursor: pointer">
      <el-table-column prop="timestamp" label="时间" width="170" sortable="custom">
        <template #default="{ row }">{{ formatTime(row.timestamp) }}</template>
      </el-table-column>
      <el-table-column prop="course_name" label="课程" min-width="100" />
      <el-table-column label="学生" width="160">
        <template #default="{ row }">
          <span v-if="row.student" class="student-link">
            <span style="font-weight: 500">{{ row.student.name }}</span>
            <span style="color: #9ca3af; font-size: 12px; margin-left: 6px">{{ row.student.student_no }}</span>
          </span>
          <span v-else style="color: #9ca3af">-</span>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <span :class="['status-tag', row.status]">
            {{ row.status === 'success' ? '成功' : '失败' }}
          </span>
        </template>
      </el-table-column>
      <el-table-column prop="confidence" label="置信度" width="95" sortable="custom" align="center">
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
      <el-table-column label="情绪" width="130">
        <template #default="{ row }">
          <span v-if="row.emotion_type" class="emotion-cell">
            <span class="emotion-icon">{{ EMOTION_ICONS[row.emotion_type] || '' }}</span>
            {{ row.emotion_type }}
          </span>
          <span v-else style="color: #9ca3af">-</span>
        </template>
      </el-table-column>
      <el-table-column prop="message" label="备注" min-width="140" show-overflow-tooltip />
    </el-table>

    <div v-if="rows.length > 20" class="pagination-wrapper">
      <el-pagination
        v-model:current-page="currentPage"
        :page-size="pageSize"
        :total="rows.length"
        layout="prev, pager, next"
        small
      />
    </div>
    <StudentDetail v-model:visible="detailVisible" :student-id="detailStudentId" />
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { Download, Search } from '@element-plus/icons-vue'
import { attendanceApi } from '../api/modules'
import StudentDetail from '../components/StudentDetail.vue'

const EMOTION_ICONS = {
  happy: '😊',
  sad: '😢',
  angry: '😠',
  surprised: '😮',
  fearful: '😨',
  disgusted: '🤢',
  neutral: '😐',
}

const rows = ref([])
const filters = reactive({ keyword: '', status: '' })
const currentPage = ref(1)
const pageSize = ref(20)
const detailVisible = ref(false)
const detailStudentId = ref(null)

function formatTime(ts) {
  if (!ts) return '-'
  const d = new Date(ts)
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

const paginatedRows = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  return rows.value.slice(start, start + pageSize.value)
})

function onSort({ prop, order }) {
  if (!prop || !order) return
  rows.value.sort((a, b) => {
    const va = a[prop] ?? 0
    const vb = b[prop] ?? 0
    return order === 'ascending' ? va - vb : vb - va
  })
}

async function load() {
  currentPage.value = 1
  const { data } = await attendanceApi.records(filters)
  rows.value = data
}

function showDetail(student) {
  if (student?.id) {
    detailStudentId.value = student.id
    detailVisible.value = true
  }
}

function showDetailFromRow(row) {
  if (row.student?.id) {
    detailStudentId.value = row.student.id
    detailVisible.value = true
  }
}

async function download() {
  const { data } = await attendanceApi.export(filters)
  const url = URL.createObjectURL(data)
  const a = document.createElement('a')
  a.href = url
  a.download = 'attendance.xlsx'
  a.click()
  URL.revokeObjectURL(url)
}

onMounted(load)
</script>

<style scoped>
.pagination-wrapper {
  display: flex;
  justify-content: center;
  margin-top: 16px;
}

.student-link {
  cursor: pointer;
}

.student-link:hover span:first-child {
  color: var(--primary, #2563eb);
}

/* 情绪列 */
.emotion-cell {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  white-space: nowrap;
}

.emotion-icon {
  font-size: 18px;
  line-height: 1;
}

/* 表格覆盖 */
:deep(.el-table) {
  border-radius: 10px !important;
  overflow: hidden;
}

:deep(.el-table th.el-table__cell) {
  background: #f8fafc !important;
  color: #6b7280 !important;
  font-weight: 600 !important;
  font-size: 13px !important;
}

:deep(.el-table .el-table__row:hover) {
  background: #f0f7ff !important;
}

:deep(.el-table--striped .el-table__body tr.el-table__row--striped td) {
  background: #fafbfc;
}

:deep(.el-table--border) {
  border-color: #e5e7eb;
}

:deep(.el-table__body td) {
  padding: 6px 0 !important;
}
</style>
