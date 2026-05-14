<template>
  <div class="page">
    <div class="toolbar">
      <h2>考勤统计</h2>
      <div>
        <el-select v-model="selectedCourse" placeholder="请选择课程" clearable style="width: 180px; margin-right: 8px" @clear="onCourseClear" @change="onCourseChange">
          <el-option v-for="name in courseList" :key="name" :label="name" :value="name" />
        </el-select>
        <el-select v-model="selectedDate" placeholder="选择日期" clearable :disabled="!selectedCourse" style="width: 160px; margin-right: 8px" @clear="load" @change="load">
          <el-option v-for="d in dateList" :key="d" :label="d" :value="d" />
        </el-select>
        <el-button :icon="Search" @click="load">查询</el-button>
        <el-button :icon="Refresh" size="small" style="margin-left: 4px" @click="reset">刷新</el-button>
        <el-button :icon="Download" size="small" style="margin-left: 4px" type="primary" :disabled="!selectedCourse" @click="exportExcel">导出Excel</el-button>
      </div>
    </div>

    <template v-if="selectedDate">
      <div class="summary section">
        <div class="summary-stats">
          <div class="stat-card">
            <span class="stat-label">应到</span>
            <span class="stat-value">{{ totalCount }}</span>
          </div>
          <div class="stat-card">
            <span class="stat-label">实到</span>
            <span class="stat-value signed">{{ signedCount }}</span>
          </div>
          <div class="stat-card">
            <span class="stat-label">缺勤</span>
            <span class="stat-value absent">{{ absentCount }}</span>
          </div>
          <div class="stat-card rate">
            <span class="stat-label">到课率</span>
            <span class="stat-value">{{ attendanceRate }}%</span>
          </div>
        </div>
        <div v-if="absentList.length" class="absent-list">
          <span class="absent-label">未签到学生：</span>
          <el-tag v-for="s in absentList" :key="s.student_no" type="danger" size="small" effect="plain" style="margin: 2px 4px 2px 0">
            {{ s.name }}（{{ s.student_no }}）
          </el-tag>
        </div>
      </div>
    </template>

    <div class="section">
      <div v-if="!selectedDate" ref="chartRef" class="chart" />
      <el-table :data="rows" style="margin-top: 16px">
        <el-table-column type="index" label="#" width="50" />
        <el-table-column prop="student_no" label="学号">
          <template #default="{ row }">
            <span class="student-link" @click="showDetail(row)">{{ row.student_no }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="name" label="姓名">
          <template #default="{ row }">
            <span class="student-link" @click="showDetail(row)">{{ row.name }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="class_name" label="班级" />
        <el-table-column :label="selectedDate ? '签到状态' : '出勤天数'" width="120">
          <template #default="{ row }">
            <template v-if="selectedDate">
              <el-tag v-if="row.count" type="success" effect="plain">已签到</el-tag>
              <el-tag v-else type="danger" effect="plain">未签到</el-tag>
            </template>
            <el-tag v-else :type="row.count > 10 ? 'success' : row.count > 5 ? 'primary' : row.count > 0 ? 'info' : 'danger'" effect="plain">
              {{ row.count }} 天
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
    </div>
    <StudentDetail v-model:visible="detailVisible" :student-id="detailStudentId" />
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { Download, Refresh, Search } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import { statisticsApi } from '../api/modules'
import StudentDetail from '../components/StudentDetail.vue'

const rows = ref([])
const courseList = ref([])
const dateList = ref([])
const selectedCourse = ref('')
const selectedDate = ref('')
const detailVisible = ref(false)
const detailStudentId = ref(null)
const chartRef = ref(null)
let chart = null

const signedList = computed(() => rows.value.filter((r) => r.count))
const absentList = computed(() => rows.value.filter((r) => !r.count))
const totalCount = computed(() => rows.value.length)
const signedCount = computed(() => signedList.value.length)
const absentCount = computed(() => absentList.value.length)
const attendanceRate = computed(() => {
  if (!rows.value.length) return 0
  return ((signedCount.value / rows.value.length) * 100).toFixed(1)
})

function showDetail(row) {
  if (row.id) {
    detailStudentId.value = row.id
    detailVisible.value = true
  }
}

async function load() {
  const { data } = await statisticsApi.attendanceStats(selectedCourse.value, selectedDate.value)
  rows.value = data
  if (!selectedDate.value && data.length) await nextTick(); renderChart(data)
}

function renderChart(data) {
  if (!chartRef.value) return
  if (!chart) chart = echarts.init(chartRef.value)
  chart.setOption({
    tooltip: { trigger: 'axis' },
    xAxis: { data: data.slice(0, 30).map(r => r.name), axisLabel: { rotate: 45, fontSize: 11 } },
    yAxis: { name: '出勤天数' },
    series: [{ type: 'bar', data: data.slice(0, 30).map(r => r.count), itemStyle: { color: '#409eff' } }],
    grid: { bottom: 100 }
  })
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

function reset() {
  selectedCourse.value = ''
  selectedDate.value = ''
  dateList.value = []
  load()
}

async function exportExcel() {
  if (!selectedCourse.value) return
  const { data } = await statisticsApi.attendanceExport(selectedCourse.value)
  const url = URL.createObjectURL(data)
  const a = document.createElement('a')
  a.href = url
  a.download = `${selectedCourse.value}-考勤统计.xlsx`
  a.click()
  URL.revokeObjectURL(url)
}

onMounted(() => {
  loadCourses()
  load()
})
</script>

<style scoped>
.summary {
  margin-bottom: 16px;
}

.summary-stats {
  display: flex;
  gap: 16px;
  margin-bottom: 12px;
}

.stat-card {
  background: #f9fafb;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 12px 20px;
  text-align: center;
  min-width: 100px;
}

.stat-card.rate {
  background: #eff6ff;
  border-color: #bfdbfe;
}

.stat-label {
  display: block;
  font-size: 12px;
  color: #6b7280;
  margin-bottom: 4px;
}

.stat-value {
  font-size: 24px;
  font-weight: 700;
  color: #111827;
}

.stat-value.signed {
  color: #059669;
}

.stat-value.absent {
  color: #dc2626;
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

.absent-label {
  font-size: 13px;
  font-weight: 500;
  color: #991b1b;
  margin-right: 4px;
}

.student-link { cursor: pointer; }
.student-link:hover { color: #2563eb; }
</style>
