<template>
  <div class="page">
    <div class="toolbar">
      <h2>总览</h2>
      <el-button :icon="Refresh" size="small" @click="load">刷新</el-button>
    </div>
    <div class="grid">
      <div class="metric">
        <div class="icon-wrapper" style="background:#dbeafe;color:#2563eb">
          <el-icon size="22"><User /></el-icon>
        </div>
        <div class="label">学生总数</div>
        <div class="value" style="color:#2563eb">{{ stats.total_students }}</div>
      </div>
      <div class="metric">
        <div class="icon-wrapper" style="background:#d1fae5;color:#10b981">
          <el-icon size="22"><Check /></el-icon>
        </div>
        <div class="label">成功签到</div>
        <div class="value" style="color:#10b981">{{ stats.success_count }}</div>
      </div>
      <div class="metric">
        <div class="icon-wrapper" style="background:#fee2e2;color:#ef4444">
          <el-icon size="22"><Close /></el-icon>
        </div>
        <div class="label">失败记录</div>
        <div class="value" style="color:#ef4444">{{ stats.failed_count }}</div>
      </div>
      <div class="metric">
        <div class="icon-wrapper" style="background:#ede9fe;color:#8b5cf6">
          <el-icon size="22"><Histogram /></el-icon>
        </div>
        <div class="label">活动参与</div>
        <div class="value" style="color:#8b5cf6">{{ stats.activity_count }}</div>
      </div>
    </div>

    <div class="section" style="margin-top: 16px">
      <h3 style="margin:0 0 12px;font-size:15px;font-weight:600">最近考勤记录</h3>
      <el-table :data="recentRecords" v-if="recentRecords.length" size="small" max-height="320" @row-click="showPhoto">
        <el-table-column prop="timestamp" label="时间" width="170" />
        <el-table-column label="学生">
          <template #default="{ row }">
            <span v-if="row.student" class="student-link">{{ row.student.name }}</span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <span :class="['status-tag', row.status]" style="white-space: nowrap">
              {{ row.status === 'success' ? '成功' : '失败' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="confidence" label="置信度" width="90" />
        <el-table-column prop="course_name" label="课程" />
      </el-table>
      <el-empty v-else description="暂无考勤记录" :image-size="80" />
    </div>

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
import { onMounted, reactive, ref } from 'vue'
import { Check, Close, Histogram, Refresh, User } from '@element-plus/icons-vue'
import { statisticsApi, attendanceApi } from '../api/modules'

const photoVisible = ref(false)
const photoUrl = ref('')
const photoRecord = ref(null)

function formatTime(ts) {
  if (!ts) return '-'
  const d = new Date(ts)
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

function showPhoto(row) {
  photoUrl.value = row.photo_url || ''
  photoRecord.value = row
  photoVisible.value = true
}

const stats = reactive({ total_students: 0, success_count: 0, failed_count: 0, activity_count: 0 })
const recentRecords = ref([])

async function load() {
  const [statsResp, recordsResp] = await Promise.all([
    statisticsApi.dashboard(),
    attendanceApi.records({ limit: 8 }),
  ])
  Object.assign(stats, statsResp.data)
  recentRecords.value = recordsResp.data
}

onMounted(load)
</script>
