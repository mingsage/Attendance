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

    <div class="section" style="margin-top: 20px">
      <h3 style="margin:0 0 14px;font-size:16px;font-weight:600">最近考勤记录</h3>
      <el-table :data="recentRecords" v-if="recentRecords.length" size="small" max-height="320">
        <el-table-column prop="timestamp" label="时间" width="170" />
        <el-table-column label="学生">
          <template #default="{ row }">
            <span v-if="row.student" class="student-link" @click="showDetail(row.student)">{{ row.student.name }}</span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <span :class="['status-tag', row.status]">
              {{ row.status === 'success' ? '成功' : '失败' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="confidence" label="置信度" width="90" />
        <el-table-column prop="course_name" label="课程" />
      </el-table>
      <el-empty v-else description="暂无考勤记录" :image-size="80" />
    </div>
    <StudentDetail v-model:visible="detailVisible" :student-id="detailStudentId" />
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { Check, Close, Histogram, Refresh, User } from '@element-plus/icons-vue'
import { statisticsApi, attendanceApi } from '../api/modules'
import StudentDetail from '../components/StudentDetail.vue'

const detailVisible = ref(false)
const detailStudentId = ref(null)

function showDetail(student) {
  if (student?.id) {
    detailStudentId.value = student.id
    detailVisible.value = true
  }
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
