<template>
  <div class="page">
    <div class="toolbar"><h2>课程管理</h2><el-button type="primary" @click="openCreate">新建课程</el-button></div>
    <el-table :data="courses" class="section" stripe>
      <el-table-column prop="name" label="课程名" />
      <el-table-column prop="school_year" label="学年" width="120" />
      <el-table-column prop="semester" label="学期" width="120" />
      <el-table-column label="操作" width="250">
        <template #default="{row}">
          <el-button size="small" @click="publishSession(row)">发布考勤</el-button>
          <el-button size="small" @click="editCourse(row)">编辑</el-button>
          <el-button size="small" type="danger" @click="deleteCourse(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
    <!-- 编辑课程 -->
    <el-dialog v-model="courseDialog" :title="editingCourse ? '编辑课程' : '新建课程'" width="420px">
      <el-form label-width="70px">
        <el-form-item label="课程名"><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="学年"><el-input v-model="form.school_year" placeholder="如 2025-2026" /></el-form-item>
        <el-form-item label="学期"><el-input v-model="form.semester" placeholder="如 2025-2026-2" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="courseDialog=false">取消</el-button><el-button type="primary" @click="saveCourse">保存</el-button></template>
    </el-dialog>
    <!-- 发布考勤（含群组创建+选人） -->
    <el-dialog v-model="sessionDialog" title="发布考勤活动" width="560px">
      <el-form label-width="70px">
        <el-form-item label="日期"><el-date-picker v-model="sess.date" type="date" style="width:100%" /></el-form-item>
        <el-form-item label="课次"><el-input v-model="sess.session_no" placeholder="如 第3周周一第1-2节" /></el-form-item>
        <el-form-item label="类型">
          <el-select v-model="sess.type" style="width:100%"><el-option label="日常考勤" value="camera" /><el-option label="合照考勤" value="group_photo" /><el-option label="手动考勤" value="manual" /></el-select>
        </el-form-item>
        <el-divider />
        <el-form-item label="参与学生">
          <div style="width:100%">
            <!-- 已有群组快速选择 -->
            <el-select v-model="sess.group_id" placeholder="选择已有群组（可选）" clearable style="width:100%;margin-bottom:8px" @change="onGroupSelect">
              <el-option v-for="g in groupList" :key="g.id" :label="`${g.name} (${g.member_count}人)`" :value="g.id" />
            </el-select>
            <!-- 或新建群组+选学生 -->
            <el-input v-model="newGroupName" placeholder="或输入新群组名" style="margin-bottom:8px" />
            <el-input v-model="studentSearch" placeholder="搜索学号/姓名加入群组" @change="searchStudents">
              <template #append><el-button @click="searchStudents">搜索</el-button></template>
            </el-input>
            <div v-if="searchResults.length" style="margin-top:6px;max-height:160px;overflow-y:auto">
              <el-checkbox-group v-model="selectedStudentIds">
                <div v-for="s in searchResults" :key="s.id" style="padding:2px 0">
                  <el-checkbox :value="s.id">{{ s.student_no }} {{ s.name }} ({{ s.class_name }})</el-checkbox>
                </div>
              </el-checkbox-group>
            </div>
            <div v-if="selectedStudentIds.length" style="margin-top:4px;color:#6b7280;font-size:12px">已选 {{ selectedStudentIds.length }} 人</div>
          </div>
        </el-form-item>
      </el-form>
      <template #footer><el-button @click="sessionDialog=false">取消</el-button><el-button type="primary" @click="doPublish">发布</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { courseApi, sessionApi, groupApi, studentApi } from '../api/modules'

const courses = ref([]); const groupList = ref([])
const courseDialog = ref(false); const editingCourse = ref(null); const form = reactive({ name: '', school_year: '', semester: '' })
const sessionDialog = ref(false); const pubCourse = ref(null)
const sess = reactive({ date: '', session_no: '', type: 'camera', group_id: null })
const newGroupName = ref('')
const studentSearch = ref(''); const searchResults = ref([]); const selectedStudentIds = ref([])

async function load() { const { data } = await courseApi.list(); courses.value = data }
async function loadGroups() { const { data } = await groupApi.list(); groupList.value = data }
function openCreate() { editingCourse.value = null; form.name=''; form.school_year=''; form.semester=''; courseDialog.value = true }
function editCourse(r) { editingCourse.value=r; form.name=r.name; form.school_year=r.school_year; form.semester=r.semester; courseDialog.value=true }
async function saveCourse() {
  if (editingCourse.value) await courseApi.update(editingCourse.value.id, { ...form })
  else await courseApi.create({ ...form })
  courseDialog.value = false; await load()
}
async function deleteCourse(r) { await ElMessageBox.confirm(`删除课程"${r.name}"？`); await courseApi.delete(r.id); await load() }

function publishSession(r) {
  pubCourse.value=r; sess.date=''; sess.session_no=''; sess.type='camera'; sess.group_id=null
  newGroupName.value=''; studentSearch.value=''; searchResults.value=[]; selectedStudentIds.value=[]
  sessionDialog.value=true
}

async function searchStudents() {
  if (!studentSearch.value) return
  const { data } = await studentApi.list(studentSearch.value); searchResults.value = data
}

function onGroupSelect(id) {
  if (id) { newGroupName.value = ''; selectedStudentIds.value = [] }
}

async function doPublish() {
  let groupId = sess.group_id
  // 如果没有选已有群组，但有新群组名+选学生 → 创建群组
  if (!groupId && newGroupName.value && selectedStudentIds.value.length) {
    const { data: g } = await groupApi.create({ name: newGroupName.value })
    await groupApi.addMembers(g.id, selectedStudentIds.value)
    groupId = g.id
  }
  if (!groupId) { ElMessage.warning('请选择或创建参与群组'); return }
  await sessionApi.create({ course_id: pubCourse.value.id, date: sess.date, session_no: sess.session_no, type: sess.type, group_id: groupId })
  sessionDialog.value = false; ElMessage.success('考勤活动已发布'); await loadGroups()
}

onMounted(() => { load(); loadGroups() })
</script>
