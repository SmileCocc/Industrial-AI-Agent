<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { ElButton, ElInput } from 'element-plus'
import { ArrowUp, Boxes, CalendarDays, ChartNoAxesCombined, History, MessageSquare, PackageSearch, Plus, RefreshCw, Wrench } from 'lucide-vue-next'
import IndustrialBlueprint from '../components/assistant/IndustrialBlueprint.vue'
import AssistantTurn from '../components/assistant/AssistantTurn.vue'
import { useAssistantStore } from '../stores/assistant'

const s = useAssistantStore()
const prompts = [
  { icon: CalendarDays, text: '今天的生产计划完成得怎么样？' },
  { icon: PackageSearch, text: '哪些工单存在缺料风险？' },
  { icon: Boxes, text: '哪些物料低于安全库存？' },
  { icon: Wrench, text: '近七天有哪些设备异常？' },
  { icon: ChartNoAxesCombined, text: '分析今天的生产效率及影响因素。' },
]
const showHistory = ref(false), input = ref<InstanceType<typeof ElInput>>(), thread = ref<HTMLElement>()
const elapsed = ref(0), disabled = computed(() => s.sending || s.loading || !!s.detailError)
watch(() => s.sending, (pending, _, cleanup) => {
  if (!pending) return
  const tick = () => { elapsed.value = Math.max(0, Math.floor((Date.now() - s.started) / 1000)) }
  tick(); const timer = window.setInterval(tick, 1000); cleanup(() => clearInterval(timer))
}, { immediate: true })
watch(() => [s.turns.length, s.id], async () => { await nextTick(); if (thread.value) thread.value.scrollTop = thread.value.scrollHeight })
onMounted(() => { void s.list() })
function edit(text: string) { s.draft = text; nextTick(() => input.value?.focus()) }
function select(id: string) { showHistory.value = false; void s.open(id) }
function fresh() { showHistory.value = false; s.fresh(); edit('') }
function keydown(event: Event) {
  if (event instanceof KeyboardEvent && event.key === 'Enter' && (event.ctrlKey || event.metaKey) && !event.isComposing) { event.preventDefault(); void s.send() }
}
</script>
<template>
  <section class="assistant" aria-label="生产助手"><div class="layout">
    <aside class="history" :class="{ expanded: showHistory }"><header><span><History :size="17"/>历史会话</span><button class="icon" title="刷新历史" aria-label="刷新历史" :disabled="s.listing" @click="s.list()"><RefreshCw :size="15"/></button><button class="toggle" :aria-expanded="showHistory" @click="showHistory = !showHistory">{{ showHistory ? '收起' : '展开' }}</button></header>
      <button class="new" :disabled="s.sending" @click="fresh"><Plus :size="16"/>新建会话</button>
      <div class="list"><p v-if="s.listError" role="alert">{{ s.listError }} <button class="link" @click="s.list()">重试</button></p><p v-else-if="s.listing && !s.history.length">正在读取历史…</p><p v-else-if="!s.history.length">提问后，会话将保存在这里。</p>
        <button v-for="row in s.history" :key="row.id" class="row" :class="{ current: row.id === s.id }" :aria-current="row.id === s.id ? 'true' : undefined" :disabled="s.sending" :title="row.title" @click="select(row.id)"><MessageSquare :size="15"/><span><b>{{ row.title }}</b><time :datetime="row.updated_at">{{ row.updated_at.slice(0,16).replace('T',' ') }}</time></span></button>
        <button v-if="s.more" class="link" :disabled="s.listing" @click="s.list(true)">加载更多</button>
      </div>
    </aside>
    <main class="work"><div v-if="s.loading || s.detailError" class="notice" role="status">{{ s.detailError || '正在读取会话…' }}<ElButton v-if="s.detailError && s.id" @click="s.open(s.id)">重新加载</ElButton></div>
      <div v-else-if="!s.turns.length" class="home"><IndustrialBlueprint/><h3>快捷提问</h3><div class="prompts"><button v-for="p in prompts" :key="p.text" @click="edit(p.text)"><component :is="p.icon" :size="17"/>{{ p.text }}</button></div></div>
      <div v-else ref="thread" class="thread" aria-label="对话记录"><AssistantTurn v-for="(t,i) in s.turns" :key="`${s.id}-${i}`" :turn="t" :busy="disabled" @recover="edit"/><div v-if="s.sending" class="wait"><span role="status">正在等待分析结果</span><time>{{ elapsed }} 秒</time><small>复杂查询可能需要几分钟。</small></div></div>
      <form class="composer" @submit.prevent="s.send()"><ElInput ref="input" v-model="s.draft" type="textarea" :autosize="{ minRows: 2, maxRows: 7 }" resize="none" maxlength="4000" :disabled="disabled" aria-label="输入生产问题" placeholder="输入问题，可附上工单号或物料编码…" @keydown="keydown"/><footer><small>Ctrl / ⌘ + Enter 发送</small><ElButton native-type="submit" type="primary" :disabled="disabled || !s.draft.trim()"><ArrowUp :size="16"/>发送</ElButton></footer></form>
    </main>
  </div></section>
</template>
<style scoped>
.assistant{container:assistant / inline-size;color:#20364a;font-family:'Source Sans 3','Microsoft YaHei',sans-serif}.layout{display:grid;grid-template-columns:minmax(155px,21%) minmax(0,1fr);border:1px solid #dae4eb;border-radius:14px;background:#fff;overflow:hidden}.history{min-width:0;padding:18px 12px;background:#f5f8fa;border-right:1px solid #dce6ec}.history header,.history header span,.new,.prompts button,.icon{display:flex;align-items:center}.history header{gap:6px;margin-bottom:15px}.history header span{gap:7px;font-weight:650;font-size:14px;margin-right:auto}.assistant button{font-family:inherit;cursor:pointer}.assistant button:disabled{cursor:default;opacity:.6}.assistant button:focus-visible,.composer:focus-within{outline:2px solid #287cb6;outline-offset:-2px}.icon,.toggle,.link{border:0;background:none;color:#476881;padding:4px}.new{justify-content:center;gap:6px;width:100%;background:white;border:1px solid #c3d4df;border-radius:6px;padding:9px;color:#244f6d;font-weight:600}.toggle{display:none}.list{margin-top:15px;max-height:60vh;overflow-y:auto}.list p,.notice{color:#657888;font-size:13px;line-height:1.7}.row{display:flex;align-items:flex-start;gap:8px;text-align:left;padding:11px 7px;width:100%;border:0;border-radius:6px;background:none;color:#3f5869}.row svg{flex-shrink:0;margin-top:2px}.row span{min-width:0}.row b,.row time{display:block}.row b{font-size:13px;font-weight:500;white-space:nowrap;text-overflow:ellipsis;overflow:hidden}.row time{margin-top:4px;color:#64798a;font-size:11px}.row.current,.row:hover{background:#e5eef4}.work{min-width:0;padding:clamp(15px,2.7vw,40px);display:flex;flex-direction:column;gap:22px}.home h3{font-size:15px;margin:22px 0 10px}.prompts{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}.prompts button{padding:10px 12px;gap:9px;text-align:left;border:1px solid #dce5ea;border-radius:7px;background:#fff;color:#304d62;font-size:13px;line-height:1.55}.prompts svg{flex-shrink:0;color:#457999}.prompts button:hover,.new:hover{background:#edf5fa;border-color:#9fbfce}.composer{border:1px solid #b9ccd8;border-radius:10px;padding:9px;background:white;margin-top:auto}.composer :deep(.el-textarea__inner){box-shadow:none;padding:6px;background:transparent}.composer footer{display:flex;align-items:center;justify-content:space-between;gap:9px;margin-top:6px}.composer small,.wait small{color:#627686;font-size:12px}.composer :deep(.el-button--primary){--el-button-bg-color:#1466a3;--el-button-border-color:#1466a3}.thread{max-height:clamp(280px,60vh,800px);min-height:260px;overflow:auto;padding-right:5px}.wait{display:flex;flex-wrap:wrap;align-items:center;gap:8px;font-size:14px;color:#365e7e}.wait time{font-variant-numeric:tabular-nums}.notice{display:grid;justify-items:start;gap:12px}.assistant .toggle{font-size:12px}
@container assistant (max-width:725px){.layout{grid-template-columns:minmax(0,1fr)}.history{display:grid;grid-template-columns:1fr auto;gap:8px;border-right:0;border-bottom:1px solid #dce6ec;padding:9px 12px}.history header{margin:0}.history header span{margin-right:3px}.toggle{display:block}.history .new{width:auto;padding:6px 10px}.list{display:none;margin:0;grid-column:1/-1;max-height:210px}.expanded .list{display:block}.work{padding:16px;gap:16px}}
@container assistant (max-width:475px){.prompts{grid-template-columns:1fr}.work{padding:12px}.home h3{margin-top:15px}.prompts button{padding:8px 10px}.composer small{font-size:11px}}
</style>
