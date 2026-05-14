<template>
  <div class="page">
    <div class="toolbar"><h2>我的人脸</h2></div>
    <div class="section">
      <el-descriptions v-if="profile" :column="1" border>
        <el-descriptions-item label="学号">{{ profile.student_no }}</el-descriptions-item>
        <el-descriptions-item label="姓名">{{ profile.name }}</el-descriptions-item>
        <el-descriptions-item label="人脸状态">
          <el-tag :type="statusType" effect="plain">{{ statusText }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="已录入照片">{{ profile.face_sample_count || 0 }} 张</el-descriptions-item>
      </el-descriptions>
      <div style="margin-top:16px; display:flex; gap:12px">
        <el-button type="primary" @click="uploadFace">上传人脸照片</el-button>
        <el-button v-if="profile?.has_face" @click="verifyFace">自拍验证</el-button>
      </div>
      <input ref="fileInput" hidden type="file" accept="image/png,image/jpeg" @change="handleUpload" />
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { studentApi } from '../api/modules'

const profile = ref(null)
const fileInput = ref(null)

const statusType = computed(() => ({ pending: 'warning', approved: 'success', rejected: 'danger' }[profile.value?.face_status] || 'info'))
const statusText = computed(() => ({ pending: '待审核', approved: '已通过', rejected: '已驳回' }[profile.value?.face_status] || '未录入'))

async function load() { try { const { data } = await studentApi.selfProfile(); profile.value = data } catch {} }

function uploadFace() { fileInput.value?.click() }
async function handleUpload(e) {
  const file = e.target?.files?.[0]; if (!file) return
  try { await studentApi.selfFace(file); ElMessage.success('人脸上传成功'); await load() }
  catch (err) { ElMessage.error(err.response?.data?.detail || '上传失败') }
  e.target.value = ''
}
async function verifyFace() {
  try { const video = await navigator.mediaDevices.getUserMedia({ video: true, audio: false })
    // simple: use hidden video + canvas
    const v = document.createElement('video'); v.srcObject = video; await v.play()
    await new Promise(r => setTimeout(r, 500))
    const c = document.createElement('canvas'); c.width = v.videoWidth; c.height = v.videoHeight
    c.getContext('2d').drawImage(v,0,0); video.getTracks().forEach(t=>t.stop())
    c.toBlob(async (blob) => {
      const { data } = await studentApi.selfVerify(new File([blob], 'verify.jpg', { type: 'image/jpeg' }))
      ElMessage.info(data.verified ? `验证通过，相似度 ${(data.similarity*100).toFixed(1)}%` : `验证未通过`)
    }, 'image/jpeg')
  } catch { ElMessage.error('摄像头调用失败') }
}

onMounted(load)
</script>
