import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const routes = [
  { path: '/login', component: () => import('../views/Login.vue') },
  {
    path: '/',
    component: () => import('../layout/MainLayout.vue'),
    children: [
      { path: '', redirect: '/dashboard' },
      { path: 'dashboard', component: () => import('../views/Dashboard.vue') },
      // 学生
      { path: 'attendance', component: () => import('../views/Attendance.vue') },
      { path: 'my-attendance', component: () => import('../views/MyAttendance.vue') },
      { path: 'my-face', component: () => import('../views/MyFace.vue') },
      // 教师
      { path: 'records', component: () => import('../views/Records.vue') },
      { path: 'students', component: () => import('../views/Students.vue') },
      { path: 'groups', component: () => import('../views/GroupManage.vue') },
      { path: 'courses', component: () => import('../views/CourseManage.vue') },
      { path: 'group-photo', component: () => import('../views/GroupPhoto.vue') },
      // 通用
      { path: 'emotion-stats', component: () => import('../views/EmotionStats.vue') },
      { path: 'activity-stats', component: () => import('../views/ActivityStats.vue') },
    ],
  },
]

const router = createRouter({ history: createWebHistory(), routes })

router.beforeEach((to) => {
  const auth = useAuthStore()
  if (to.path !== '/login' && !auth.isLoggedIn) return '/login'
  if (to.path === '/login' && auth.isLoggedIn) {
    return auth.role === 'teacher' ? '/dashboard' : '/attendance'
  }
  // 学生不允许访问教师页面
  const teacherOnly = ['/records', '/students', '/groups', '/courses', '/group-photo']
  if (auth.role === 'student' && teacherOnly.includes(to.path)) return '/attendance'
  return true
})

export default router
