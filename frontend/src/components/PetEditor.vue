<template>
  <div class="pet-card">
    <div class="pet-head">
      <input v-model="pet.name" class="name-input" placeholder="宠物名称" />
      <button class="btn-ghost" @click="$emit('remove')">删除</button>
    </div>
    <div class="states">
      <div class="state-row" v-for="st in states" :key="st.key">
        <span class="state-label">{{ st.label }}</span>
        <select v-model="pet.assets[st.key]" @change="onSample(st.key)">
          <option value="">— 选示例素材 —</option>
          <option v-for="f in samples" :key="f" :value="f">{{ f }}</option>
        </select>
        <label class="upload-btn">
          上传
          <input type="file" accept="image/*" @change="onUpload(st.key, $event)" hidden />
        </label>
        <span class="hint" v-if="pet.files && pet.files[st.key]">
          已上传: {{ pet.files[st.key].name }}
        </span>
      </div>
    </div>
  </div>
</template>

<script setup>
const props = defineProps({ pet: Object, samples: Array })
defineEmits(['remove'])

const states = [
  { key: 'crawl', label: '爬行' },
  { key: 'climb', label: '攀爬' },
  { key: 'sit', label: '发呆' },
  { key: 'happy', label: '开心' },
]

function onSample(key) {
  // 选了示例素材则清除该状态的上传文件
  if (props.pet.files) props.pet.files[key] = null
}

function onUpload(key, e) {
  const file = e.target.files[0]
  if (!file) return
  if (!props.pet.files) props.pet.files = {}
  props.pet.files[key] = file
  props.pet.assets[key] = file.name // config 引用文件名，后端据此保存
}
</script>

<style scoped>
.pet-card {
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 14px;
  padding: 14px 16px;
  margin-bottom: 14px;
}
.pet-head {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}
.name-input {
  flex: 1;
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid rgba(255, 255, 255, 0.12);
  color: #eee;
  border-radius: 8px;
  padding: 8px 10px;
  font-size: 14px;
}
.states { display: flex; flex-direction: column; gap: 8px; }
.state-row { display: flex; align-items: center; gap: 10px; }
.state-label {
  width: 48px; color: #9fb3c8; font-size: 13px; flex-shrink: 0;
}
.state-row select {
  flex: 1; background: rgba(0, 0, 0, 0.3); color: #eee;
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 8px; padding: 6px 8px; font-size: 13px;
}
.upload-btn {
  background: rgba(120, 160, 255, 0.15);
  border: 1px solid rgba(120, 160, 255, 0.4);
  color: #bcd0ff; border-radius: 8px; padding: 6px 12px;
  font-size: 13px; cursor: pointer; white-space: nowrap;
}
.hint { font-size: 12px; color: #7fd1a0; }
</style>
