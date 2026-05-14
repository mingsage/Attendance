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
    <!-- 编辑弹窗 -->
    <el-dialog v-model="courseDialog" :title="editingCourse ? '编辑课程' : '新建课程'" width="420px">
      <el-form label-width="70px">
        <el-form-item label="课程名"><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="学年"><el-input v-model="form.school_year" placeholder="如 2025-2026" /></el-form-item>
        <el-form-item label="学期"><el-input v-model="form.semester" placeholder="如 2025-2026-2" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="courseDialog=false">取消</el-button><el-button type="primary" @click="saveCourse">保存</el-button></template>
    </el-dialog>
    <!-- 发布考勤弹窗 -->
    <el-dialog v-model="sessionDialog" title="发布考勤活动" width="480px">
      <el-form label-width="70px">
        <el-form-item label="日期"><el-date-picker v-model="sess.date" type="date" /></el-form-item>
        <el-form-item label="课次"><el-input v-model="sess.session_no" placeholder="如 第3周周一第1-2节" /></el-form-item>
        <el-form-item label="类型">
          <el-select v-model="sess.type"><el-option label="日常考勤" value="camera" /><el-option label="合照考勤" value="group_photo" /><el-option label="手动考勤" value="manual" /></el-select>
        </el-form-item>
        <el-form-item label="群组">
          <el-select v-model="sess.group_id" placeholder="选择参与群组"><el-option v-for="g in groupList" :key="g.id" :label="`${g.name} (${g.member_count}人)`" :value="g.id" /></el-select>
        </el-form-item>
      </el-form>
      <template #footer><el-button @click="sessionDialog=false">取消</el-button><el-button type="primary" @click="doPublish">发布</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { courseApi, sessionApi, groupApi } from '../api/modules'

const courses = ref([]); const groupList = ref([])
const courseDialog = ref(false); const editingCourse = ref(null); const form = reactive({ name: '', school_year: '', semester: '' })
const sessionDialog = ref(false); const pubCourse = ref(null); const sess = reactive({ date: '', session_no: '', type: 'camera', group_id: null })

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
function publishSession(r) { pubCourse.value=r; sess.date=''; sess.session_no=''; sess.type='camera'; sess.group_id=null; sessionDialog.value=true }
async function doPublish() {
  await sessionApi.create({ course_id: pubCourse.value.id, date: sess.date, session_no: sess.session_no, type: sess.type, group_id: sess.group_id })
  sessionDialog.value = false; ElMessage.success('考勤活动已发布')
}

onMounted(() => { load(); loadGroups() })
</script>
