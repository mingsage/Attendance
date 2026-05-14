<template>
  <div class="login-page">
    <div class="login-bg" />
    <div class="login-card">
      <div class="login-header">
        <div class="logo">
          <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
            <rect width="40" height="40" rx="10" fill="#2563eb" />
            <path d="M20 12c-3.3 0-6 2.7-6 6s2.7 6 6 6 6-2.7 6-6-2.7-6-6-6zm0 9c-1.7 0-3-1.3-3-3s1.3-3 3-3 3 1.3 3 3-1.3 3-3 3zm-8 11c0-4.4 3.6-8 8-8s8 3.6 8 8" stroke="#fff" stroke-width="2.5" fill="none" stroke-linecap="round" />
          </svg>
        </div>
        <h1>班级考勤系统</h1>
        <p class="subtitle">智能人脸识别签到管理平台</p>
      </div>
      <el-form class="login-form" :model="form" @keyup.enter="submit">
        <el-form-item>
          <el-input v-model="form.username" prefix-icon="User" placeholder="用户名" size="large" />
        </el-form-item>
        <el-form-item>
          <el-input v-model="form.password" prefix-icon="Lock" placeholder="密码" show-password size="large" />
        </el-form-item>
        <el-button type="primary" :loading="loading" size="large" class="login-btn" @click="submit">登 录</el-button>
      </el-form>
      <p class="login-hint">
        默认教师账号：<code>teacher / 123456</code>
      </p>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const auth = useAuthStore()
const loading = ref(false)
const form = reactive({ username: 'teacher', password: '123456' })

async function submit() {
  loading.value = true
  try {
    await auth.login(form)
    router.push(auth.role === 'student' ? '/my-profile' : '/dashboard')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: grid;
  place-items: center;
  position: relative;
  overflow: hidden;
}

.login-bg {
  position: absolute;
  inset: 0;
  background: linear-gradient(135deg, #1e3a8a 0%, #2563eb 30%, #7c3aed 70%, #a855f7 100%);
  opacity: 0.08;
}

.login-card {
  position: relative;
  width: 400px;
  padding: 40px 36px 32px;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(20px);
  border: 1px solid rgba(255, 255, 255, 0.6);
  border-radius: 16px;
  box-shadow: 0 20px 60px rgba(15, 23, 42, 0.15);
  animation: fadeIn 0.5s ease;
}

.login-header {
  text-align: center;
  margin-bottom: 32px;
}

.logo {
  display: flex;
  justify-content: center;
  margin-bottom: 16px;
}

h1 {
  margin: 0;
  font-size: 24px;
  font-weight: 700;
  color: #111827;
}

.subtitle {
  margin: 6px 0 0;
  font-size: 14px;
  color: #6b7280;
}

.login-form {
  margin-bottom: 8px;
}

.login-btn {
  width: 100%;
  height: 44px;
  font-size: 15px;
  font-weight: 600;
  letter-spacing: 2px;
}

.login-hint {
  margin: 16px 0 0;
  text-align: center;
  font-size: 13px;
  color: #9ca3af;
}

.login-hint code {
  background: #f3f4f6;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
  color: #6b7280;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(16px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
