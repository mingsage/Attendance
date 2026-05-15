<template>
  <div class="face-overlay-wrap" ref="wrap">
    <img ref="img" :src="src" class="face-overlay-img" :class="imgClass" :style="imgStyle" @load="onLoad" />
    <div v-if="ready" class="face-overlay-layer" :style="layerStyle">
      <div
        v-for="(f, i) in faces"
        :key="i"
        class="face-overlay-box"
        :class="{ matched: f.recognized }"
        :style="boxStyle(f.bbox)"
      >
        <span class="face-overlay-label">{{ f.recognized ? (f.name || '✓') : '?' }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'

const props = defineProps({
  src: { type: String, required: true },
  faces: { type: Array, default: () => [] },
  imgClass: { type: String, default: '' },
  maxHeight: { type: String, default: '' },
})

const img = ref(null)
const wrap = ref(null)
const ready = ref(false)
const layerStyle = ref({})
let natural = { w: 1, h: 1 }

const imgStyle = computed(() => (props.maxHeight ? { maxHeight: props.maxHeight } : {}))

function onLoad() {
  if (!img.value) return
  natural = { w: img.value.naturalWidth, h: img.value.naturalHeight }
  syncLayer()
  ready.value = true
}

function syncLayer() {
  const el = img.value
  if (!el) return
  layerStyle.value = {
    width: el.clientWidth + 'px',
    height: el.clientHeight + 'px',
  }
}

function boxStyle(bbox) {
  const el = img.value
  if (!el) return {}
  const sx = el.clientWidth / natural.w
  const sy = el.clientHeight / natural.h
  return {
    left: bbox[0] * sx + 'px',
    top: bbox[1] * sy + 'px',
    width: bbox[2] * sx + 'px',
    height: bbox[3] * sy + 'px',
  }
}
</script>

<style scoped>
.face-overlay-wrap {
  position: relative;
  display: inline-block;
  line-height: 0;
}

.face-overlay-img {
  display: block;
  border-radius: 8px;
}

.face-overlay-layer {
  position: absolute;
  top: 0;
  left: 0;
  pointer-events: none;
}

.face-overlay-box {
  position: absolute;
  border: 2px solid #ef4444;
  border-radius: 4px;
}

.face-overlay-box.matched {
  border-color: #10b981;
}

.face-overlay-label {
  position: absolute;
  bottom: -20px;
  left: 0;
  font-size: 11px;
  font-weight: 600;
  color: #fff;
  background: rgba(0, 0, 0, 0.65);
  padding: 1px 5px;
  border-radius: 3px;
  white-space: nowrap;
  line-height: 1.4;
  pointer-events: none;
}
</style>
