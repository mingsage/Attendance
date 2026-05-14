<template>
  <el-container class="shell">
    <el-aside width="236px" class="sidebar">
      <div class="brand">
        <svg width="28" height="28" viewBox="0 0 40 40" fill="none">
          <rect width="40" height="40" rx="10" fill="#2563eb" />
          <path d="M20 12c-3.3 0-6 2.7-6 6s2.7 6 6 6 6-2.7 6-6-2.7-6-6-6zm0 9c-1.7 0-3-1.3-3-3s1.3-3 3-3 3 1.3 3 3-1.3 3-3 3zm-8 11c0-4.4 3.6-8 8-8s8 3.6 8 8" stroke="#fff" stroke-width="2.5" fill="none" stroke-linecap="round" />
        </svg>
        <span>班级考勤系统</span>
      </div>
      <el-menu
        router
        :default-active="$route.path"
        background-color="#111827"
        text-color="#9ca3af"
        active-text-color="#ffffff"
      >
        <el-menu-item index="/dashboard">
          <el-icon><DataBoard /></el-icon>
          <span>总览</span>
        </el-menu-item>
        <el-menu-item v-if="auth.role === 'teacher'" index="/attendance">
          <el-icon><Camera /></el-icon>
          <span>考勤签到</span>
        </el-menu-item>
        <el-menu-item index="/records">
          <el-icon><Tickets /></el-icon>
          <span>考勤记录</span>
        </el-menu-item>
        <el-menu-item v-if="auth.role === 'teacher'" index="/students">
          <el-icon><User /></el-icon>
          <span>学生管理</span>
        </el-menu-item>
        <el-menu-item v-if="auth.role === 'teacher'" index="/group-photo">
          <el-icon><Picture /></el-icon>
          <span>合照识别</span>
        </el-menu-item>
        <el-menu-item v-if="auth.role === 'student'" index="/my-profile">
          <el-icon><UserFilled /></el-icon>
          <span>我的人脸</span>
        </el-menu-item>
        <el-menu-item index="/emotion-stats">
          <el-icon><TrendCharts /></el-icon>
          <span>情绪统计</span>
        </el-menu-item>
        <!-- 考勤统计已合并到考勤记录 -->
      </el-menu>
    </el-aside>
    <el-container>
      <el-header class="topbar">
        <div class="topbar-left">
          <span class="page-title">{{ routeTitle }}</span>
        </div>
        <div class="topbar-right">
          <span class="user-info">
            <el-icon><User /></el-icon>
            {{ auth.username }}
          </span>
          <el-tag v-if="auth.role === 'teacher'" size="small" type="primary" effect="plain">教师</el-tag>
          <el-tag v-else size="small" effect="plain">学生</el-tag>
          <el-button :icon="SwitchButton" size="small" @click="logout">退出</el-button>
        </div>
      </el-header>
      <el-main>
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { computed } from 'vue'
import { SwitchButton, User, UserFilled } from '@element-plus/icons-vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const routeTitles = {
  '/dashboard': '总览面板',
  '/attendance': '考勤签到',
  '/records': '考勤记录',
  '/students': '学生管理',
  '/group-photo': '合照识别',
  '/emotion-stats': '情绪统计',
}

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

const routeTitle = computed(() => routeTitles[route.path] || '')

function logout() {
  auth.logout()
  router.push('/login')
}
</script>

<style scoped>
.shell {
  min-height: 100vh;
}

.sidebar {
  background: #111827;
  display: flex;
  flex-direction: column;
}

.brand {
  height: 60px;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 18px;
  color: #fff;
  font-weight: 700;
  font-size: 15px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  flex-shrink: 0;
}

.el-menu {
  border-right: none !important;
  flex: 1;
}

.el-menu-item {
  margin: 2px 8px;
  border-radius: 8px !important;
  transition: all 0.15s ease;
}

.el-menu-item.is-active {
  background: rgba(37, 99, 235, 0.2) !important;
  font-weight: 600;
}

.el-menu-item:hover {
  background: rgba(255, 255, 255, 0.06) !important;
}

.el-menu-item .el-icon {
  font-size: 18px;
  margin-right: 4px;
}

.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #fff;
  border-bottom: 1px solid #e5e7eb;
  padding: 0 24px;
  height: 60px !important;
}

.topbar-left {
  display: flex;
  align-items: center;
}

.page-title {
  font-size: 16px;
  font-weight: 600;
  color: #111827;
}

.topbar-right {
  display: flex;
  align-items: center;
  gap: 10px;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 14px;
  color: #374151;
}
</style>
