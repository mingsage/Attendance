<template>
  <div class="page">
    <div class="toolbar">
      <h2>情绪统计</h2>
      <el-button :icon="Refresh" size="small" @click="load">刷新</el-button>
    </div>
    <div class="section">
      <div ref="chartRef" class="chart" />
      <el-table :data="records" style="margin-top: 16px" @row-click="showPhoto">
        <el-table-column prop="timestamp" label="时间" width="180">
          <template #default="{ row }">{{ formatTime(row.timestamp) }}</template>
        </el-table-column>
        <el-table-column prop="student_no" label="学号" />
        <el-table-column prop="name" label="姓名" />
        <el-table-column label="情绪" width="130">
          <template #default="{ row }">
            <span style="white-space: nowrap">{{ EMOTION_MAP[row.emotion_type] || row.emotion_type }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="confidence" label="置信度" width="130">
          <template #default="{ row }">
            {{ row.confidence?.toFixed(3) }}
          </template>
        </el-table-column>
        <el-table-column prop="source" label="来源" />
      </el-table>
    </div>
    <StudentDetail v-model:visible="detailVisible" :student-id="detailStudentId" />

    <!-- 签到照片弹窗 -->
    <el-dialog v-model="photoVisible" title="签到照片" width="420px" destroy-on-close>
      <div v-if="photoUrl" class="photo-preview">
        <img :src="photoUrl" style="width: 100%; border-radius: 8px; display: block" />
        <div class="photo-info">
          <p><strong>时间：</strong>{{ formatTime(photoRecord?.timestamp) }}</p>
          <p><strong>情绪：</strong>{{ EMOTION_MAP[photoRecord?.emotion_type] || photoRecord?.emotion_type }}</p>
          <p v-if="photoRecord?.source"><strong>来源：</strong>{{ photoRecord.source }}</p>
        </div>
      </div>
      <div v-else style="text-align: center; color: #999; padding: 40px">
        暂无签到照片
      </div>
    </el-dialog>
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
const photoVisible = ref(false)
const photoUrl = ref('')
const photoRecord = ref(null)

function showDetail(row) {
  if (row.student_id) {
    detailStudentId.value = row.student_id
    detailVisible.value = true
  }
}

function showPhoto(row) {
  photoUrl.value = row.photo_url || ''
  photoRecord.value = row
  photoVisible.value = true
}

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
</style>
