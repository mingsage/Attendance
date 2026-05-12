<template>
  <div class="page">
    <div class="toolbar">
      <h2>情绪统计</h2>
      <el-button :icon="Refresh" size="small" @click="load">刷新</el-button>
    </div>
    <div class="section">
      <div ref="chartRef" class="chart" />
      <el-table :data="records" style="margin-top: 16px">
        <el-table-column prop="timestamp" label="时间" width="180">
          <template #default="{ row }">{{ formatTime(row.timestamp) }}</template>
        </el-table-column>
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
        <el-table-column prop="emotion_type" label="情绪" />
        <el-table-column prop="confidence" label="置信度" />
        <el-table-column prop="source" label="来源" />
      </el-table>
    </div>
    <StudentDetail v-model:visible="detailVisible" :student-id="detailStudentId" />
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import { emotionApi, statisticsApi } from '../api/modules'
import StudentDetail from '../components/StudentDetail.vue'

const detailVisible = ref(false)
const detailStudentId = ref(null)

function showDetail(row) {
  if (row.student_id) {
    detailStudentId.value = row.student_id
    detailVisible.value = true
  }
}

const EMOTION_COLORS = {
  happy: '#10b981',
  sad: '#6366f1',
  angry: '#ef4444',
  surprised: '#f59e0b',
  fearful: '#8b5cf6',
  disgusted: '#84cc16',
  neutral: '#9ca3af',
}

const EMOTION_LABELS = {
  happy: '开心',
  sad: '悲伤',
  angry: '生气',
  surprised: '惊讶',
  fearful: '恐惧',
  disgusted: '厌恶',
  neutral: '中性',
}

const chartRef = ref()
const records = ref([])
let chart

function formatTime(ts) {
  if (!ts) return '-'
  const d = new Date(ts)
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

async function load() {
  const [{ data }, recordsResp] = await Promise.all([statisticsApi.emotion(), emotionApi.records({ limit: 100 })])
  records.value = recordsResp.data
  chart ||= echarts.init(chartRef.value)
  chart.setOption({
    tooltip: { trigger: 'item', formatter: '{b}: {c} 次 ({d}%)' },
    legend: {
      bottom: 0,
      data: data.map((item) => EMOTION_LABELS[item.name] || item.name),
    },
    series: [{
      type: 'pie',
      radius: ['40%', '70%'],
      center: ['50%', '45%'],
      avoidLabelOverlap: true,
      label: {
        show: true,
        formatter: '{b}\n{d}%',
        fontSize: 12,
      },
      emphasis: {
        label: { show: true, fontSize: 14, fontWeight: 'bold' },
        itemStyle: { shadowBlur: 10, shadowOffsetX: 0, shadowColor: 'rgba(0,0,0,0.2)' },
      },
      data: data.map((item) => ({
        ...item,
        name: EMOTION_LABELS[item.name] || item.name,
        itemStyle: { color: EMOTION_COLORS[item.name] || '#9ca3af' },
      })),
    }],
  })
}

onMounted(load)
</script>

<style scoped>
.student-link { cursor: pointer; }
.student-link:hover { color: #2563eb; }
</style>
