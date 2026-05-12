import http from './http'

export const authApi = {
  login: (data) => http.post('/auth/login', data),
  register: (data) => http.post('/auth/register', data)
}

export const studentApi = {
  list: (keyword = '') => http.get('/students', { params: { keyword } }),
  get: (id) => http.get(`/students/${id}`),
  getByNo: (studentNo) => http.get(`/students/by-no/${studentNo}`),
  create: (data) => http.post('/students', data),
  update: (id, data) => http.put(`/students/${id}`, data),
  remove: (id) => http.delete(`/students/${id}`),
  uploadFace: (id, file) => {
    const form = new FormData()
    form.append('file', file)
    return http.post(`/students/${id}/face`, form)
  },
  batchUploadFaces: (files) => {
    const form = new FormData()
    files.forEach((file) => form.append('files', file))
    return http.post('/students/faces/batch', form)
  }
}

export const attendanceApi = {
  challenge: () => http.get('/attendance/liveness-challenge'),
  livenessSettings: () => http.get('/attendance/liveness-settings'),
  updateLivenessSettings: (enabled) => http.put('/attendance/liveness-settings', null, { params: { enabled } }),
  checkIn: (file, courseName) => {
    const form = new FormData()
    form.append('file', file)
    return http.post('/attendance/check-in', form, { params: { course_name: courseName } })
  },
  records: (params) => http.get('/attendance/records', { params }),
  export: (params) => http.get('/attendance/export', { params, responseType: 'blob' })
}

export const groupPhotoApi = {
  recognize: (file, activityName) => {
    const form = new FormData()
    form.append('file', file)
    return http.post('/group-photo/recognize', form, { params: { activity_name: activityName } })
  }
}

export const statisticsApi = {
  dashboard: () => http.get('/statistics/dashboard'),
  emotion: () => http.get('/statistics/emotion'),
  activity: () => http.get('/statistics/activity'),
  attendanceStats: (courseName = '', date = '') => http.get('/statistics/attendance-stats', { params: { course_name: courseName, attendance_date: date } }),
  courseList: () => http.get('/statistics/course-list'),
  courseDates: (courseName = '') => http.get('/statistics/course-dates', { params: { course_name: courseName } }),
  attendanceExport: (courseName) => http.get('/statistics/attendance-export', { params: { course_name: courseName }, responseType: 'blob' })
}

export const emotionApi = {
  records: (params) => http.get('/emotions/records', { params })
}
