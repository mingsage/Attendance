<template>
  <el-dialog v-model="dialogVisible" title="学生详情" width="520px" destroy-on-close @closed="onClosed">
    <div v-if="student" class="detail-wrap">
      <div class="detail-photo">
        <el-image
          v-if="student.face_image_url"
          :src="student.face_image_url"
          fit="cover"
          style="width: 200px; height: 240px; border-radius: 8px;"
        >
          <template #error>
            <div class="photo-placeholder">无照片</div>
          </template>
        </el-image>
        <div v-else class="photo-placeholder">无照片</div>
      </div>
      <el-descriptions :column="1" border style="flex:1">
        <el-descriptions-item label="学号">{{ student.student_no }}</el-descriptions-item>
        <el-descriptions-item label="姓名">{{ student.name }}</el-descriptions-item>
        <el-descriptions-item label="性别">{{ student.gender || '-' }}</el-descriptions-item>
        <el-descriptions-item label="专业/班级">{{ student.class_name }}</el-descriptions-item>
        <el-descriptions-item label="人脸状态">
          <el-tag v-if="student.has_face" type="success" effect="plain" size="small">已录入</el-tag>
          <el-tag v-else type="warning" effect="plain" size="small">未录入</el-tag>
        </el-descriptions-item>
      </el-descriptions>
    </div>
    <div v-else class="loading-wrap">
      <span>加载中...</span>
    </div>
  </el-dialog>
</template>

<script setup>
import { ref, watch } from 'vue'
import { studentApi } from '../api/modules'

const props = defineProps({
  studentId: { type: Number, default: null },
  studentNo: { type: String, default: '' },
  visible: { type: Boolean, default: false },
})

const emit = defineEmits(['update:visible'])

const student = ref(null)
const dialogVisible = ref(false)

async function fetchStudent() {
  student.value = null
  try {
    const { data } = props.studentId
      ? await studentApi.get(props.studentId)
      : props.studentNo
        ? await studentApi.getByNo(props.studentNo)
        : Promise.reject()
    student.value = data
  } catch {
    student.value = null
  }
}

watch(() => props.visible, (val) => {
  dialogVisible.value = val
  if (val) fetchStudent()
})

watch(dialogVisible, (val) => {
  if (!val) emit('update:visible', false)
})

function onClosed() {
  student.value = null
}
</script>

<style scoped>
.detail-wrap {
  display: flex;
  gap: 24px;
  align-items: flex-start;
}

.detail-photo {
  flex-shrink: 0;
  width: 200px;
  height: 240px;
}

.photo-placeholder {
  width: 200px;
  height: 240px;
  border-radius: 8px;
  background: #f3f4f6;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #9ca3af;
  font-size: 14px;
}

.loading-wrap {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 40px 0;
  color: #6b7280;
}
</style>
