<script setup lang="ts">
import { computed } from 'vue'
import MarkdownIt from 'markdown-it'
import DOMPurify from 'dompurify'
import { Workflow, TriangleAlert } from 'lucide-vue-next'
import type { Turn } from '../../stores/assistant'
const props = defineProps<{ turn: Turn; busy: boolean }>()
defineEmits<{ recover: [question: string] }>()
const md = new MarkdownIt({ html: false, breaks: true }).disable('image')
const html = computed(() => DOMPurify.sanitize(md.render(props.turn.answer || ''), { USE_PROFILES: { html: true } }))
const metrics = computed(() => {
  const out: { label: string; value: string }[] = []
  const add = (label: string, value: number | undefined | null, unit = '') => {
    if (typeof value === 'number' && Number.isFinite(value)) out.push({ label, value: value.toLocaleString('zh-CN') + unit })
  }
  const data = props.turn.analysis_data, total = data?.plan?.total ?? data?.efficiency?.total
  add('今日计划量', total?.planned); add('今日实际量', total?.actual); add('累计完成率', total?.rate_pct, '%')
  add('库存预警物料', data?.inventory?.count, ' 种'); add('近七日设备报警', data?.equipment?.alarm_count, ' 次')
  add('缺料工单', props.turn.shortage_data?.shortage_order_count, ' 张')
  return out
})
</script>
<template>
  <article><p class="question">{{ turn.question }}</p>
    <template v-if="turn.answer || turn.detail"><h3><Workflow :size="17"/> 生产助手 <small v-if="turn.duration_ms != null">{{ (turn.duration_ms / 1000).toFixed(1) }} 秒</small></h3>
      <div v-if="turn.detail" class="error"><TriangleAlert :size="17"/><div>{{ turn.detail }}<br><button :disabled="busy" @click="$emit('recover', turn.question)">重新编辑问题</button></div></div>
      <dl v-if="metrics.length"><div v-for="item in metrics" :key="item.label"><dt>{{ item.label }}</dt><dd>{{ item.value }}</dd></div></dl>
      <div v-if="html" class="markdown" v-html="html"/>
      <details v-if="turn.trace?.length" class="trace"><summary>执行轨迹（{{ turn.trace.length }} 步）</summary>
        <ol><li v-for="e in turn.trace" :key="e.seq"><details><summary>{{ e.summary }} <small>{{ e.system }} {{ e.duration_ms != null ? `${e.duration_ms} ms` : '' }}</small></summary><pre>{{ JSON.stringify(e, null, 2) }}</pre></details></li></ol>
      </details>
    </template>
  </article>
</template>
<style scoped>
article{color:#20364a;margin-bottom:24px;min-width:0}.question{margin:0 0 18px auto;padding:11px 16px;border-radius:13px 13px 3px 13px;background:#eaf3f8;width:fit-content;max-width:85%;white-space:pre-wrap;overflow-wrap:anywhere}h3{font-size:15px;display:flex;align-items:center;gap:8px;margin:0 0 10px}small{font-size:12px;color:#637583;font-weight:400}.markdown{line-height:1.75;overflow-x:auto;overflow-wrap:anywhere;font-size:14px}.markdown :deep(table){border-collapse:collapse;min-width:65%;font-size:13px}.markdown :deep(th),.markdown :deep(td){border:1px solid #d8e1e7;text-align:left;padding:7px 10px}.markdown :deep(th){background:#edf3f6}.markdown :deep(pre),pre{background:#f3f6f8;overflow:auto;padding:12px;border-radius:5px}.markdown :deep(a){color:#12649b}dl{display:flex;flex-wrap:wrap;gap:6px}dl div{padding:10px 14px;background:#f2f6f8;border-left:2px solid #9bbdcc}dt,summary{font-size:13px}dd{margin:4px 0 0;font-weight:650;font-size:20px}.trace{border-top:1px solid #dde5e9;padding:12px 0;color:#475f72}.trace li{padding:4px}.trace pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px}summary,button{cursor:pointer}.error{display:flex;gap:10px;padding:14px;background:#fff5e7;border-radius:8px;color:#734610}.error svg{flex-shrink:0}.error button{border:0;background:none;color:inherit;text-decoration:underline;padding:8px 0 0}
</style>
