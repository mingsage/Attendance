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
      { path: 'attendance', component: () => import('../views/Attendance.vue') },
      { path: 'records', component: () => import('../views/Records.vue') },
      { path: 'students', component: () => import('../views/Students.vue') },
      { path: 'group-photo', component: () => import('../views/GroupPhoto.vue') },
      { path: 'emotion-stats', component: () => import('../views/EmotionStats.vue') },
      { path: 'activity-stats', redirect: '/records' }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to) => {
  const auth = useAuthStore()
  if (to.path !== '/login' && !auth.isLoggedIn) return '/login'
  if (to.path === '/login' && auth.isLoggedIn) return '/dashboard'
  return true
})

export default router
