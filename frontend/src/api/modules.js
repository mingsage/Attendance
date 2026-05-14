import http from './http'

export const authApi = {
  login: (data) => http.post('/auth/login', data),
}

export const studentApi = {
  list: (keyword = '') => http.get('/students', { params: { keyword } }),
  get: (id) => http.get(`/students/${id}`),
  getByNo: (studentNo) => http.get(`/students/by-no/${studentNo}`),
  create: (data) => http.post('/students', data),
  update: (id, data) => http.put(`/students/${id}`, data),
  remove: (id) => http.delete(`/students/${id}`),
  batchDelete: (ids) => http.post('/students/batch-delete', { student_ids: ids }),
  uploadFace: (id, file) => {
    const form = new FormData(); form.append('file', file)
    return http.post(`/students/${id}/face`, form)
  },
  batchUploadFaces: (files) => {
    const form = new FormData(); files.forEach(f => form.append('files', f))
    return http.post('/students/faces/batch', form)
  },
  batchCreateAccounts: (data) => http.post('/students/batch-accounts', data),
  selfFace: (file) => { const f = new FormData(); f.append('file', file); return http.post('/students/self/face', f) },
  selfVerify: (file) => { const f = new FormData(); f.append('file', file); return http.post('/students/self/verify', f) },
  selfProfile: () => http.get('/students/self/profile'),
}

export const attendanceApi = {
  recognize: (file) => { const f = new FormData(); f.append('file', file); return http.post('/attendance/recognize', f) },
  checkIn: (file, courseName, sessionId, challengeAction) => {
    const form = new FormData(); form.append('file', file)
    const params = { course_name: courseName }
    if (sessionId) params.session_id = sessionId
    if (challengeAction) params.challenge_action = challengeAction
    return http.post('/attendance/check-in', form, { params })
  },
  challenge: () => http.get('/attendance/liveness-challenge'),
  livenessSettings: () => http.get('/attendance/liveness-settings'),
  updateLivenessSettings: (enabled) => http.put('/attendance/liveness-settings', null, { params: { enabled } }),
  records: (params) => http.get('/attendance/records', { params }),
  myRecords: (params) => http.get('/attendance/records/mine', { params }),
  deleteRecord: (id) => http.delete(`/attendance/records/${id}`),
  batchDeleteRecords: (ids) => http.post('/attendance/records/batch-delete', { ids }),
  manualRecord: (data) => http.post('/attendance/records/manual', data),
  export: (params) => http.get('/attendance/export', { params, responseType: 'blob' }),
}

export const groupPhotoApi = {
  recognize: (file, activityName) => {
    const form = new FormData(); form.append('file', file)
    return http.post('/group-photo/recognize', form, { params: { activity_name: activityName } })
  },
  save: (data) => http.post('/group-photo/save', data),
}

export const groupApi = {
  list: () => http.get('/groups'),
  create: (data) => http.post('/groups', data),
  get: (id) => http.get(`/groups/${id}`),
  update: (id, data) => http.put(`/groups/${id}`, data),
  delete: (id) => http.delete(`/groups/${id}`),
  addMembers: (id, student_ids) => http.post(`/groups/${id}/members`, { student_ids }),
  removeMember: (groupId, studentId) => http.delete(`/groups/${groupId}/members/${studentId}`),
}

export const courseApi = {
  list: () => http.get('/courses'),
  create: (data) => http.post('/courses', data),
  update: (id, data) => http.put(`/courses/${id}`, data),
  delete: (id) => http.delete(`/courses/${id}`),
}

export const sessionApi = {
  listActive: () => http.get('/sessions/active'),
  create: (data) => http.post('/sessions', data),
  get: (id) => http.get(`/sessions/${id}`),
}

export const supplementApi = {
  create: (data) => http.post('/supplements', data),
  list: (status) => http.get('/supplements', { params: { status } }),
  mine: () => http.get('/supplements/mine'),
  approve: (id) => http.put(`/supplements/${id}/approve`),
  reject: (id) => http.put(`/supplements/${id}/reject`),
}

export const statisticsApi = {
  dashboard: () => http.get('/statistics/dashboard'),
  emotion: () => http.get('/statistics/emotion'),
  activity: () => http.get('/statistics/activity'),
  attendanceStats: (courseName = '', date = '') =>
    http.get('/statistics/attendance-stats', { params: { course_name: courseName, attendance_date: date } }),
  courseList: () => http.get('/statistics/course-list'),
  courseDates: (courseName = '') => http.get('/statistics/course-dates', { params: { course_name: courseName } }),
  attendanceExport: (courseName) =>
    http.get('/statistics/attendance-export', { params: { course_name: courseName }, responseType: 'blob' }),
}

export const emotionApi = {
  records: (params) => http.get('/emotions/records', { params }),
}
