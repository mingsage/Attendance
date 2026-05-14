<template>
  <div class="page">
    <div class="toolbar"><h2>我的考勤</h2></div>
    <div class="summary section">
      <div class="stat-card"><span class="stat-label">应到</span><span class="stat-value">{{ summary.total }}</span></div>
      <div class="stat-card"><span class="stat-label">已签</span><span class="stat-value signed">{{ summary.attended }}</span></div>
      <div class="stat-card"><span class="stat-label">缺签</span><span class="stat-value absent">{{ summary.missed }}</span></div>
      <div class="stat-card rate"><span class="stat-label">到课率</span><span class="stat-value">{{ summary.rate }}</span></div>
    </div>
    <el-table :data="allRows" class="section" stripe>
      <el-table-column type="index" label="#" width="50" />
      <el-table-column label="日期" width="120"><template #default="{row}">{{ row.date }}</template></el-table-column>
      <el-table-column prop="course_name" label="课程" />
      <el-table-column prop="session_no" label="课次" width="160" />
      <el-table-column label="状态" width="90">
        <template #default="{row}"><el-tag :type="row.attended ? 'success' : 'danger'" effect="plain">{{ row.attended ? '已签' : '缺签' }}</el-tag></template>
      </el-table-column>
      <el-table-column label="操作" width="120">
        <template #default="{row}">
          <el-button v-if="!row.attended" size="small" type="warning" @click="applySupplement(row)">申请补录</el-button>
        </template>
      </el-table-column>
    </el-table>
    <div class="table-footer">共 {{ allRows.length }} 条</div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { attendanceApi, supplementApi } from '../api/modules'

const summary = ref({ total: 0, attended: 0, missed: 0, rate: '0%' })
const attendedList = ref([])
const missedList = ref([])

const allRows = computed(() => [
  ...attendedList.value.map(r => ({ ...r, attended: true, date: formatDate(r.timestamp), course_name: r.course_name || '-' })),
  ...missedList.value.map(r => ({ ...r, attended: false })),
])

function formatDate(ts) { if(!ts) return '-'; const d=new Date(ts); return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}` }

async function load() {
  const { data } = await attendanceApi.myRecords()
  attendedList.value = data.attended
  missedList.value = data.missed
  summary.value = data.summary
}

async function applySupplement(row) {
  try {
    await supplementApi.create({ session_id: row.session_id, reason: '漏签申请补录' })
    ElMessage.success('补录申请已提交')
  } catch (e) { ElMessage.error(e.response?.data?.detail || '申请失败') }
}

onMounted(load)
</script>

<style scoped>
.summary { display: flex; gap: 16px; margin-bottom: 12px }
.stat-card { background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 8px; padding: 12px 20px; text-align: center; min-width: 100px }
.stat-card.rate { background: #eff6ff; border-color: #bfdbfe }
.stat-label { display: block; font-size: 12px; color: #6b7280; margin-bottom: 4px }
.stat-value { font-size: 24px; font-weight: 700; color: #111827 }
.stat-value.signed { color: #059669 }
.stat-value.absent { color: #dc2626 }
.table-footer { text-align: center; color: #9ca3af; font-size: 13px; margin-top: 8px }
</style>
