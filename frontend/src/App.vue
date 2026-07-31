<template>
  <div class="page">
    <header class="hero">
      <h1>🐵 Brother Pet 生成器</h1>
      <p>设置动图（支持 PNG / GIF）与参数，一键打包成桌面宠物 exe</p>
    </header>

    <section class="panel">
      <h2>全局设置</h2>
      <div class="grid">
        <label class="field">
          <span>输出 exe 路径</span>
          <input v-model="outputPath" placeholder="C:\Users\你\Desktop\BrotherPet.exe" />
        </label>
        <label class="field">
          <span>素材来源</span>
          <select v-model="generator">
            <option value="local">本地素材（示例/上传）</option>
            <option value="openai" :disabled="true">OpenAI 自动生成（需配置 key）</option>
          </select>
        </label>
        <label class="field">
          <span>投喂台词</span>
          <input v-model="feedText" placeholder="感谢爸爸投喂！" />
        </label>
        <label class="field">
          <span>爬行速度 (帧/秒)</span>
          <input type="number" v-model.number="crawlSpeed" min="2" max="20" />
        </label>
        <label class="field">
          <span>跳跃频率 (0~1)</span>
          <input type="number" v-model.number="jumpChance" min="0" max="1" step="0.05" />
        </label>
        <label class="field">
          <span>发呆频率 (0~0.01)</span>
          <input type="number" v-model.number="sitChance" min="0" max="0.01" step="0.0005" />
        </label>
      </div>
      <label class="field full">
        <span>叫爸爸台词（每行一条）</span>
        <textarea v-model="dadQuotes" rows="3"></textarea>
      </label>
    </section>

    <section class="panel">
      <div class="panel-head">
        <h2>宠物列表</h2>
        <button class="btn-ghost" @click="addPet">+ 添加宠物</button>
      </div>
      <PetEditor
        v-for="p in pets"
        :key="p.id"
        :pet="p"
        :samples="samples"
        @remove="removePet(p.id)"
      />
    </section>

    <div class="actions">
      <button class="btn-primary" :disabled="busy" @click="submit">
        {{ busy ? '生成中…' : '🚀 生成 exe' }}
      </button>
    </div>

    <section class="panel log-panel" v-if="task.id">
      <h2>任务进度 ({{ task.status }})</h2>
      <pre class="log">{{ task.logs.join('\n') || '等待…' }}</pre>
      <a
        v-if="task.status === 'done' && task.result"
        class="btn-primary"
        :href="downloadUrl(task.id)"
      >⬇️ 下载生成的 exe</a>
      <p v-if="task.error" class="err">错误：{{ task.error }}</p>
    </section>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getSamples, generate, getTask, downloadUrl } from './api.js'
import PetEditor from './components/PetEditor.vue'

const samples = ref([])
const outputPath = ref('C:\\Users\\MW\\Desktop\\BrotherPet.exe')
const feedText = ref('感谢爸爸投喂！')
const dadQuotes = ref('叫爸爸！\n爸爸~爸爸~\n爸爸我在这里！\n爸爸抱抱~\n爸爸是大英雄！\n爸爸给我买糖~')
const crawlSpeed = ref(6)
const jumpChance = ref(0.5)
const sitChance = ref(0.0015)
const generator = ref('local')

const pets = ref([
  { id: 1, name: '白T眼镜哥', assets: { crawl: 'pet1_crawl_1.png', climb: 'pet1_climb.png', sit: 'pet1_crawl_1.png', happy: 'pet1_happy.png' }, files: {} },
  { id: 2, name: '黑T恤兄弟', assets: { crawl: 'pet2_crawl.png', climb: 'pet2_crawl.png', sit: 'pet2_sit.png', happy: 'pet2_happy.png' }, files: {} },
])

const task = ref({ id: null, status: '', logs: [], result: null, error: null })
const busy = ref(false)
let pollTimer = null

onMounted(async () => {
  try {
    const r = await getSamples()
    samples.value = r.files || []
  } catch (e) {
    console.warn('获取示例素材失败', e)
  }
})

function addPet() {
  pets.value.push({
    id: Date.now(),
    name: '新宠物',
    assets: { crawl: '', climb: '', sit: '', happy: '' },
    files: {},
  })
}
function removePet(id) {
  pets.value = pets.value.filter((p) => p.id !== id)
}

async function submit() {
  const config = {
    pets: pets.value.map((p) => ({ name: p.name, assets: { ...p.assets } })),
    settings: {
      crawl_speed: crawlSpeed.value,
      jump_chance: jumpChance.value,
      sit_chance: sitChance.value,
    },
    dad_quotes: dadQuotes.value.split('\n').map((s) => s.trim()).filter(Boolean),
    feed_text: feedText.value,
    output_path: outputPath.value,
    generator: generator.value,
  }
  // 校验：每只宠物至少选了「爬行/攀爬/发呆/开心」中的任意一个素材，否则拦截
  for (const p of pets.value) {
    const a = p.assets || {}
    const has = a.crawl || a.climb || a.sit || a.happy
    if (!has) {
      alert(`宠物「${p.name || '未命名'}」还没有选素材！\n请至少选择一个动作（示例或上传）再生成，否则 exe 会提示「未加载到宠物素材」。`)
      return
    }
  }
  const files = []
  for (const p of pets.value) {
    for (const f of Object.values(p.files || {})) {
      if (f) files.push(f)
    }
  }
  busy.value = true
  task.value = { id: null, status: 'running', logs: [], result: null, error: null }
  try {
    const r = await generate(config, files)
    task.value.id = r.task_id
    startPoll()
  } catch (e) {
    task.value.status = 'error'
    task.value.error = String(e)
    busy.value = false
  }
}

function startPoll() {
  pollTimer = setInterval(async () => {
    const data = await getTask(task.value.id)
    task.value.status = data.status
    task.value.logs = data.logs
    task.value.result = data.result
    task.value.error = data.error
    if (data.status === 'done' || data.status === 'error') {
      clearInterval(pollTimer)
      busy.value = false
    }
  }, 1500)
}
</script>

<style>
* { box-sizing: border-box; }
body {
  margin: 0; font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
  background: radial-gradient(1200px 600px at 70% -10%, #2a2350, #0e0e1a 60%);
  color: #e6e6f0; min-height: 100vh;
}
</style>

<style scoped>
.page { max-width: 880px; margin: 0 auto; padding: 32px 20px 80px; }
.hero h1 { font-size: 30px; margin: 0 0 6px; }
.hero p { color: #9aa3c0; margin: 0 0 24px; }
.panel {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 16px; padding: 18px 20px; margin-bottom: 20px;
}
.panel h2 { font-size: 16px; margin: 0 0 14px; color: #cdd6f4; }
.panel-head { display: flex; align-items: center; justify-content: space-between; }
.grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.field { display: flex; flex-direction: column; gap: 6px; font-size: 13px; color: #9fb3c8; }
.field.full { grid-column: 1 / -1; margin-top: 12px; }
.field input, .field select, .field textarea {
  background: rgba(0, 0, 0, 0.3); color: #eee; border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 8px; padding: 9px 10px; font-size: 14px; font-family: inherit;
}
.actions { display: flex; justify-content: center; margin: 8px 0 24px; }
.btn-primary {
  background: linear-gradient(135deg, #7c5cff, #b06bff); color: white; border: none;
  padding: 13px 34px; border-radius: 12px; font-size: 15px; font-weight: 600;
  cursor: pointer; text-decoration: none; display: inline-block;
  box-shadow: 0 8px 24px rgba(124, 92, 255, 0.35);
}
.btn-primary:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-ghost {
  background: transparent; color: #ff9b9b; border: 1px solid rgba(255, 155, 155, 0.4);
  border-radius: 8px; padding: 6px 12px; font-size: 13px; cursor: pointer;
}
.log-panel .log {
  background: rgba(0, 0, 0, 0.45); border-radius: 10px; padding: 12px;
  font-size: 12px; line-height: 1.6; max-height: 320px; overflow: auto; white-space: pre-wrap;
}
.err { color: #ff8a8a; }
</style>
