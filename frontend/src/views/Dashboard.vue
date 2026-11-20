<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount, ref } from 'vue'
import { Activity, Gauge, CalendarDays, ClipboardList, Factory, PackageMinus, RefreshCw, Siren } from 'lucide-vue-next'
import { api } from '../api'
import DashboardPlot from '../components/dashboard/DashboardPlot.vue'

const cards = [
  { key: 'planned', name: '今日计划产量', unit: '件', icon: ClipboardList },
  { key: 'actual', name: '今日实际产量', unit: '件', icon: Factory },
  { key: 'pending_order_count', name: '待执行工单', unit: '张', icon: CalendarDays },
  { key: 'rate_pct', name: '计划完成率', unit: '%', icon: Gauge },
  { key: 'shortage_order_count', name: '今日缺料工单', unit: '张', icon: PackageMinus },
  { key: 'today_alarm_count', name: '今日新增报警', unit: '条', icon: Siren },
] as const
interface Snapshot {
  date: string
  metrics: Record<Exclude<typeof cards[number]['key'], 'rate_pct'>, number> & { rate_pct: number | null; low_stock_count: number }
  lines: { line: string; name: string; rate_pct: number | null; alarms_started_today: number }[]
  trend: { date: string; planned: number; actual: number }[]
  inventory_distribution: { category: string; count: number }[]
}
const snapshot = ref<Snapshot>()
const busy = ref(false)
const failed = ref(false)
const updated = ref('')
const controller = new AbortController()
async function refresh() {
  if (busy.value) return
  busy.value = true
  failed.value = false
  try {
    const { data } = await api.get<Snapshot>('/dashboard', { signal: controller.signal })
    if (!data?.date || !data.metrics || ![data.lines, data.trend, data.inventory_distribution].every(Array.isArray)) throw new Error('驾驶舱响应格式异常')
    // 整份快照同时替换，避免刷新时跨日期混用指标和图表。
    snapshot.value = data
    updated.value = new Date().toLocaleTimeString('zh-CN', { hour12: false })
  } catch {
    if (!controller.signal.aborted) failed.value = true
  } finally { busy.value = false }
}
onMounted(refresh)
onBeforeUnmount(() => controller.abort())
const charts = computed(() => {
  const d = snapshot.value
  if (!d) return []
  const labels = d.lines.map(l => l.name || l.line)
  return [
    { title: '每日生产趋势', description: '近 7 个自然日的计划与实际产量', dimension: '日期', unit: '件', trend: true, labels: d.trend.map(t => t.date), series: [{ name: '计划', values: d.trend.map(t => t.planned) }, { name: '实际', values: d.trend.map(t => t.actual) }] },
    { title: '各产线完成率', description: '今日实际产量 / 计划产量，未排产显示为 —', dimension: '产线', unit: '%', labels, series: [{ name: '完成率', values: d.lines.map(l => l.rate_pct) }] },
    { title: '物料库存分布', description: `按分类统计 SKU 种数，低于安全库存的物料共 ${d.metrics.low_stock_count} 种`, dimension: '物料分类', unit: '种', labels: d.inventory_distribution.map(r => r.category), series: [{ name: '物料种数', values: d.inventory_distribution.map(r => r.count) }] },
    { title: '产线报警统计', description: '各产线今日新增的报警记录', dimension: '产线', unit: '条', labels, series: [{ name: '新增报警', values: d.lines.map(l => l.alarms_started_today) }] },
  ]
})
</script>

<template>
  <section class="dashboard" aria-label="生产驾驶舱" :aria-busy="busy">
    <header class="toolbar">
      <div><h1><Activity :size="24" aria-hidden="true" />生产驾驶舱</h1><p v-if="snapshot">业务日期 {{ snapshot.date }}<span class="sep">·</span>上次刷新 {{ updated }}</p></div>
      <button type="button" :disabled="busy" @click="refresh"><RefreshCw :size="15" aria-hidden="true" />{{ busy ? '刷新中' : '刷新数据' }}</button>
    </header>
    <p v-if="failed" role="alert" class="notice">{{ snapshot ? '刷新失败，当前显示上次成功获取的数据。' : '驾驶舱数据加载失败，请点击刷新数据重试。' }}</p>
    <p v-else-if="busy && !snapshot" role="status" class="notice">正在获取生产指标…</p>
    <template v-if="snapshot">
      <div class="kpis"><article v-for="c in cards" :key="c.key" class="kpi"><div class="metric-name"><component :is="c.icon" :size="17" aria-hidden="true" />{{ c.name }}</div><div class="number">{{ snapshot.metrics[c.key]?.toLocaleString('zh-CN') ?? '—' }} <small>{{ c.unit }}</small></div></article></div>
      <div class="plots"><DashboardPlot v-for="chart in charts" :key="chart.title" v-bind="chart" /></div>
    </template>
  </section>
</template>

<style scoped>
.dashboard{--surface:#fff;--ink:#183353;--muted:#52677e;--edge:#dce5ef;--series-one:#2a78d6;--series-two:#eb6834;--accent-bg:#eaf3ff;--accent:#155aa9;min-width:0;color:var(--ink);display:grid;gap:18px;container-type:inline-size}.toolbar{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}.toolbar h1,.toolbar button,.metric-name{display:flex;align-items:center;gap:9px}.toolbar h1{margin:0;font-size:24px;letter-spacing:.02em}.toolbar h1 svg,.metric-name svg{color:var(--accent)}.toolbar p{color:var(--muted);margin:7px 0 0;font-size:13px}.sep{margin:0 8px}.toolbar button{background:var(--accent-bg);color:var(--accent);border:1px solid var(--edge);padding:9px 13px;border-radius:7px;cursor:pointer;font:inherit;font-size:13px}.toolbar button:disabled{cursor:wait}.kpis,.plots{display:grid;gap:14px}.kpis{grid-template-columns:repeat(6,minmax(0,1fr))}.plots{grid-template-columns:repeat(2,minmax(0,1fr))}.kpi,.notice{background:var(--surface);border:1px solid var(--edge);border-radius:10px;padding:16px}.metric-name{color:var(--muted);font-size:13px}.number{margin-top:12px;font:600 clamp(22px,2.2vw,34px)/1.15 'Inter','Microsoft YaHei',sans-serif;font-variant-numeric:tabular-nums;overflow-wrap:anywhere}.number small{font-size:12px;font-weight:400;color:var(--muted)}.notice{margin:0}
@container(max-width:1000px){.kpis{grid-template-columns:repeat(3,minmax(0,1fr))}}
@container(max-width:680px){.plots{grid-template-columns:minmax(0,1fr)}.kpis{grid-template-columns:repeat(2,minmax(0,1fr));gap:9px}.kpi{padding:12px}.metric-name{gap:5px}}
@media(prefers-color-scheme:dark){.dashboard{--surface:#172538;--ink:#edf4ff;--muted:#bdcada;--edge:#405268;--series-one:#3987e5;--series-two:#d95926;--accent-bg:#213a58;--accent:#97c5ff;background:#142236;padding:12px;border-radius:12px}}
</style>
