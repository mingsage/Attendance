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
    <el-table :data="paginatedRows" class="section" @sort-change="onSort">
      <el-table-column prop="timestamp" label="时间" width="180" sortable="custom">
        <template #default="{ row }">{{ formatTime(row.timestamp) }}</template>
      </el-table-column>
      <el-table-column prop="course_name" label="课程" />
      <el-table-column label="学生" min-width="140">
        <template #default="{ row }">
          <span v-if="row.student" class="student-link" @click="showDetail(row.student)">
            <span style="font-weight:500">{{ row.student.name }}</span>
            <span style="color:#9ca3af;font-size:12px;margin-left:4px">{{ row.student.student_no }}</span>
          </span>
          <span v-else>-</span>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <span :class="['status-tag', row.status]">
            {{ row.status === 'success' ? '成功' : '失败' }}
          </span>
        </template>
      </el-table-column>
      <el-table-column prop="confidence" label="置信度" width="100" sortable="custom">
        <template #default="{ row }">
          <span v-if="row.confidence !== null">{{ (row.confidence * 100).toFixed(1) }}%</span>
          <span v-else>-</span>
        </template>
      </el-table-column>
      <el-table-column prop="liveness_score" label="活体分" width="90">
        <template #default="{ row }">
          {{ row.liveness_score?.toFixed(3) || '-' }}
        </template>
      </el-table-column>
      <el-table-column prop="emotion_type" label="情绪" width="90" />
      <el-table-column prop="message" label="备注" min-width="160" show-overflow-tooltip />
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
  color: #2563eb;
}
</style>
