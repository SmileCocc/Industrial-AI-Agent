<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount, ref, watch } from 'vue'
import * as echarts from 'echarts/core'
import { BarChart, LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, AriaComponent } from 'echarts/components'
import { SVGRenderer } from 'echarts/renderers'
import { LabelLayout } from 'echarts/features'

echarts.use([BarChart, LineChart, GridComponent, TooltipComponent, AriaComponent, LabelLayout, SVGRenderer])
const props = defineProps<{
  title: string; description: string; dimension: string; unit: string; trend?: boolean
  labels: string[]; series: { name: string; values: (number | null)[] }[]
}>()
const table = ref(false)
const plot = ref<HTMLDivElement>()
const ready = computed(() => props.series.some(s => s.values.some(v => v != null)))
const height = computed(() => props.trend ? 235 : Math.max(190, 50 + props.labels.length * 30))
let instance: echarts.ECharts | undefined
let observer: ResizeObserver | undefined
const dark = window.matchMedia('(prefers-color-scheme: dark)')
function draw() {
  const el = plot.value
  if (!el || !el.clientWidth || table.value || !ready.value) return
  instance ??= echarts.init(el, undefined, { renderer: 'svg' })
  const style = getComputedStyle(el)
  const token = (name: string) => style.getPropertyValue(name).trim()
  const ink = token('--ink'), muted = token('--muted'), surface = token('--surface')
  const colors = [token('--series-one'), token('--series-two')]
  const category = { type: 'category', data: props.labels, inverse: !props.trend, axisTick: { show: false }, axisLine: { lineStyle: { color: token('--edge') } }, axisLabel: { color: muted, hideOverlap: true, width: 95, overflow: 'truncate' } }
  const value = { type: 'value', min: 0, minInterval: props.unit === '%' ? undefined : 1, axisLabel: { color: muted, hideOverlap: true }, splitLine: { lineStyle: { color: token('--edge'), type: 'dashed' } } }
  instance.resize()
  instance.setOption({
    animation: false, color: colors, aria: { enabled: true },
    textStyle: { fontFamily: 'Inter, Microsoft YaHei, sans-serif', color: ink },
    grid: { top: 16, bottom: 8, left: 4, right: props.trend ? 48 : 16, containLabel: true },
    tooltip: { trigger: 'axis', confine: true, renderMode: 'richText', axisPointer: { type: props.trend ? 'cross' : 'shadow' }, valueFormatter: (v: unknown) => v == null ? '—' : `${v} ${props.unit}` },
    xAxis: props.trend ? category : value, yAxis: props.trend ? value : category,
    series: props.series.map((s, i) => props.trend ? {
      type: 'line', name: s.name, data: s.values, symbol: i ? 'diamond' : 'circle', symbolSize: 9,
      lineStyle: { width: 2, type: i ? 'dashed' : 'solid' }, itemStyle: { borderColor: surface, borderWidth: 2 },
      endLabel: { show: true, formatter: '{a}', color: ink, fontSize: 11 }, labelLayout: { moveOverlap: 'shiftY' },
    } : { type: 'bar', name: s.name, data: s.values, barMaxWidth: 14, itemStyle: { borderRadius: [0, 4, 4, 0] } }),
  }, true)
}
onMounted(() => {
  observer = new ResizeObserver(draw)
  if (plot.value) observer.observe(plot.value)
  dark.addEventListener('change', draw)
  draw()
})
watch([() => props.series, () => props.labels, table], draw, { flush: 'post' })
onBeforeUnmount(() => { observer?.disconnect(); dark.removeEventListener('change', draw); instance?.dispose() })
</script>

<template>
  <article class="panel">
    <header><div><h3>{{ title }}</h3><p>{{ description }}</p></div><button type="button" :aria-pressed="table" :aria-label="`${title}数据表`" @click="table = !table">{{ table ? '看图表' : '数据表' }}</button></header>
    <div class="meta"><span>单位 · {{ unit }}</span><span v-if="series.length > 1" class="legend"><span v-for="(s,i) in series" :key="s.name"><i :class="{ second: i === 1 }" />{{ s.name }}</span></span></div>
    <div v-if="!ready" class="empty">暂无可绘制数据</div>
    <div v-show="!table && ready" class="scroll"><div ref="plot" :style="{height: `${height}px`}" /></div>
    <div v-if="table && labels.length" class="scroll" tabindex="0"><table :aria-label="title"><thead><tr><th>{{ dimension }}</th><th v-for="s in series" :key="s.name">{{ s.name }}（{{ unit }}）</th></tr></thead><tbody><tr v-for="(label,i) in labels" :key="i"><th scope="row">{{ label }}</th><td v-for="s in series" :key="s.name">{{ s.values[i]?.toLocaleString('zh-CN') ?? '—' }}</td></tr></tbody></table></div>
  </article>
</template>
<style scoped>
.panel{min-width:0;padding:20px;background:var(--surface);border:1px solid var(--edge);border-radius:12px;color:var(--ink)}header,.meta,.legend,.legend span{display:flex;align-items:center;gap:10px}header,.meta{justify-content:space-between}header{align-items:flex-start}h3,p{margin:0}h3{font-size:17px}p,.meta{font-size:12px;color:var(--muted)}p{margin-top:5px}button{white-space:nowrap;border:1px solid var(--edge);border-radius:6px;background:var(--surface);color:var(--ink);padding:5px 9px;cursor:pointer}.meta{margin:18px 0 2px;flex-wrap:wrap}.legend{flex-wrap:wrap}.legend span{gap:5px}.legend i{width:17px;border-top:3px solid var(--series-one)}.legend .second{border-top:3px dashed var(--series-two)}.scroll{overflow:auto;max-height:360px}.empty{text-align:center;padding:54px 0;color:var(--muted)}table{border-collapse:collapse;width:100%;font-size:13px}th,td{padding:9px 5px;text-align:right;border-bottom:1px solid var(--edge)}th:first-child{text-align:left}thead{position:sticky;top:0;background:var(--surface)}@media(forced-colors:active),print{.scroll:has(table){display:block!important}}
</style>
