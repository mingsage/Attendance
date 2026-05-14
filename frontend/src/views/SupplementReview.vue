<template>
  <div class="page">
    <div class="toolbar"><h2>补录审核</h2></div>
    <el-table :data="requests" class="section" stripe>
      <el-table-column prop="student_name" label="姓名" width="100" />
      <el-table-column prop="student_no" label="学号" width="120" />
      <el-table-column prop="session_info" label="考勤活动" min-width="180" />
      <el-table-column prop="reason" label="理由" min-width="120" />
      <el-table-column prop="created_at" label="申请时间" width="160">
        <template #default="{row}">{{ formatTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column prop="status" label="状态" width="80">
        <template #default="{row}"><el-tag :type="row.status==='pending'?'warning':'info'" effect="plain">{{ {pending:'待审',approved:'已通过',rejected:'已驳回'}[row.status] }}</el-tag></template>
      </el-table-column>
      <el-table-column label="操作" width="160">
        <template #default="{row}">
          <template v-if="row.status === 'pending'">
            <el-button size="small" type="success" @click="approve(row.id)">通过</el-button>
            <el-button size="small" type="danger" @click="reject(row.id)">驳回</el-button>
          </template>
          <span v-else style="color:#9ca3af">—</span>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { supplementApi } from '../api/modules'

const requests = ref([])

function formatTime(ts) { if(!ts) return '-'; const d=new Date(ts); const pad=n=>String(n).padStart(2,'0'); return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}` }

async function load() {
  try { const { data } = await supplementApi.list('pending'); requests.value = data } catch {}
}

async function approve(id) {
  await supplementApi.approve(id); ElMessage.success('已通过并写入考勤记录'); await load()
}
async function reject(id) {
  await supplementApi.reject(id); ElMessage.success('已驳回'); await load()
}

onMounted(load)
</script>
