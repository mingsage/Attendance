<template>
  <div class="page">
    <div class="toolbar"><h2>群组管理</h2><el-button type="primary" @click="openCreate">新建群组</el-button></div>
    <div class="section">
      <el-table :data="groups" @row-click="selectGroup" highlight-current-row stripe>
        <el-table-column prop="name" label="群组名" />
        <el-table-column prop="member_count" label="人数" width="100" />
        <el-table-column label="操作" width="200">
          <template #default="{row}"><el-button size="small" @click.stop="editGroup(row)">编辑</el-button><el-button size="small" type="danger" @click.stop="deleteGroup(row)">删除</el-button></template>
        </el-table-column>
      </el-table>
    </div>
    <div v-if="selectedGroup" class="section" style="margin-top:16px">
      <h3>{{ selectedGroup.name }} — 成员</h3>
      <div style="margin-bottom:8px">
        <el-input v-model="searchKeyword" placeholder="搜索学号/姓名" style="width:200px;margin-right:8px" />
        <el-button @click="searchStudents">搜索</el-button>
        <el-button @click="addSearched">添加选中</el-button>
      </div>
      <el-table :data="searchResults" @selection-change="onSelect" ref="searchTable" v-if="searchResults.length">
        <el-table-column type="selection" width="48" />
        <el-table-column prop="student_no" label="学号" /><el-table-column prop="name" label="姓名" /><el-table-column prop="class_name" label="班级" />
      </el-table>
      <el-table :data="members" style="margin-top:8px">
        <el-table-column prop="student_no" label="学号" /><el-table-column prop="name" label="姓名" /><el-table-column prop="class_name" label="班级" />
        <el-table-column label="操作" width="100"><template #default="{row}"><el-button size="small" type="danger" @click="removeMember(row)">移除</el-button></template></el-table-column>
      </el-table>
    </div>
    <el-dialog v-model="dialogVisible" :title="editingGroup ? '编辑群组' : '新建群组'" width="400px">
      <el-input v-model="formName" placeholder="群组名" />
      <template #footer><el-button @click="dialogVisible=false">取消</el-button><el-button type="primary" @click="saveGroup">保存</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { groupApi, studentApi } from '../api/modules'

const groups = ref([]); const selectedGroup = ref(null); const members = ref([])
const dialogVisible = ref(false); const editingGroup = ref(null); const formName = ref('')
const searchKeyword = ref(''); const searchResults = ref([]); const selectedStudents = ref([])

async function loadGroups() { const { data } = await groupApi.list(); groups.value = data }
function openCreate() { editingGroup.value = null; formName.value = ''; dialogVisible.value = true }
function editGroup(row) { editingGroup.value = row; formName.value = row.name; dialogVisible.value = true }
async function saveGroup() {
  if (editingGroup.value) await groupApi.update(editingGroup.value.id, { name: formName.value })
  else await groupApi.create({ name: formName.value })
  dialogVisible.value = false; await loadGroups()
}
async function deleteGroup(row) { await ElMessageBox.confirm(`删除群组"${row.name}"？`); await groupApi.delete(row.id); await loadGroups() }
async function selectGroup(row) { selectedGroup.value = row; const { data } = await groupApi.get(row.id); members.value = data.students }
async function searchStudents() { if (!searchKeyword.value) return; const { data } = await studentApi.list(searchKeyword.value); searchResults.value = data }
function onSelect(sel) { selectedStudents.value = sel }
async function addSearched() {
  if (!selectedGroup.value || !selectedStudents.value.length) return
  await groupApi.addMembers(selectedGroup.value.id, selectedStudents.value.map(s => s.id))
  ElMessage.success('添加成功'); await selectGroup(selectedGroup.value)
}
async function removeMember(row) { await groupApi.removeMember(selectedGroup.value.id, row.id); await selectGroup(selectedGroup.value) }

onMounted(loadGroups)
</script>
