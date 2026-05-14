<template>
  <div class="page">
    <div class="toolbar"><h2>我的信息</h2></div>
    <div class="section">
      <!-- 基本信息 -->
      <el-descriptions v-if="profile" :column="2" border title="基本信息">
        <el-descriptions-item label="学号">{{ profile.student_no }}</el-descriptions-item>
        <el-descriptions-item label="姓名">{{ profile.name }}</el-descriptions-item>
        <el-descriptions-item label="班级">{{ profile.class_name }}</el-descriptions-item>
        <el-descriptions-item label="性别">{{ profile.gender || '-' }}</el-descriptions-item>
        <el-descriptions-item label="年级">{{ profile.grade || '-' }}</el-descriptions-item>
        <el-descriptions-item label="专业">{{ profile.major || '-' }}</el-descriptions-item>
        <el-descriptions-item label="人脸状态">
          <el-tag :type="statusType" effect="plain">{{ statusText }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="已录入照片">{{ profile.face_sample_count || 0 }} 张</el-descriptions-item>
      </el-descriptions>

      <!-- 人脸管理 -->
      <div style="margin-top:16px">
        <h3>人脸管理</h3>
        <div style="display:flex;gap:12px;margin-top:8px">
          <el-button type="primary" @click="uploadFace">上传人脸照片</el-button>
          <el-button v-if="profile?.has_face" @click="verifyFace">自拍验证</el-button>
        </div>
        <input ref="fileInput" hidden type="file" accept="image/png,image/jpeg" @change="handleUpload" />
      </div>

      <!-- 修改密码 -->
      <div style="margin-top:24px">
        <h3>修改密码</h3>
        <el-form :model="pwdForm" label-width="80px" style="margin-top:12px;max-width:360px">
          <el-form-item label="原密码"><el-input v-model="pwdForm.oldPwd" type="password" show-password /></el-form-item>
          <el-form-item label="新密码"><el-input v-model="pwdForm.newPwd" type="password" show-password /></el-form-item>
          <el-form-item label="确认密码"><el-input v-model="pwdForm.confirmPwd" type="password" show-password /></el-form-item>
          <el-form-item><el-button type="primary" :disabled="!pwdOk" @click="changePwd">修改密码</el-button></el-form-item>
        </el-form>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'

const profile = ref(null)
const fileInput = ref(null)
const pwdForm = reactive({ oldPwd: '', newPwd: '', confirmPwd: '' })

const pwdOk = computed(() => pwdForm.oldPwd && pwdForm.newPwd && pwdForm.newPwd === pwdForm.confirmPwd && pwdForm.newPwd.length >= 4)
const statusType = computed(() => ({ pending:'warning', approved:'success', rejected:'danger' }[profile.value?.face_status] || 'info'))
const statusText = computed(() => ({ pending:'待审核', approved:'已通过', rejected:'已驳回' }[profile.value?.face_status] || '未录入'))

async function load() {
  try {
    const { data } = await (await import('../api/modules')).studentApi.selfProfile()
    profile.value = data
  } catch {}
}

function uploadFace() { fileInput.value?.click() }
async function handleUpload(e) {
  const file = e.target?.files?.[0]; if (!file) return
  try {
    const { studentApi } = await import('../api/modules')
    await studentApi.selfFace(file)
    ElMessage.success('上传成功')
    await load()
  } catch (err) { ElMessage.error(err.response?.data?.detail || '上传失败') }
  e.target.value = ''
}

async function verifyFace() {
  try {
    const video = await navigator.mediaDevices.getUserMedia({ video: true, audio: false })
    const v = document.createElement('video'); v.srcObject = video; await v.play()
    await new Promise(r => setTimeout(r, 600))
    const c = document.createElement('canvas'); c.width = v.videoWidth; c.height = v.videoHeight
    c.getContext('2d').drawImage(v, 0, 0); video.getTracks().forEach(t => t.stop())
    c.toBlob(async (blob) => {
      const { studentApi } = await import('../api/modules')
      const { data } = await studentApi.selfVerify(new File([blob], 'verify.jpg', { type: 'image/jpeg' }))
      ElMessage.info(data.verified ? `验证通过，相似度 ${(data.similarity*100).toFixed(1)}%` : '验证未通过')
    }, 'image/jpeg')
  } catch { ElMessage.error('摄像头调用失败') }
}

async function changePwd() {
  try {
    const http = (await import('../api/http')).default
    await http.put('/auth/change-password', { old_password: pwdForm.oldPwd, new_password: pwdForm.newPwd })
    ElMessage.success('密码修改成功')
    pwdForm.oldPwd = ''; pwdForm.newPwd = ''; pwdForm.confirmPwd = ''
  } catch (err) { ElMessage.error(err.response?.data?.detail || '修改失败') }
}

onMounted(load)
</script>
