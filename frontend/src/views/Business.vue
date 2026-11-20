<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { Search, RotateCw, ClipboardList, Boxes, Factory, BellRing, Inbox } from 'lucide-vue-next'
import { api } from '../api'

type Kind = 'orders' | 'materials' | 'lines' | 'alarms'
type Row = Record<string, unknown>
type Field = [string, string]
const config = {
  orders: { title: '生产工单', path: '/mes/work-orders', id: 'wo_no', icon: ClipboardList, cols: [['wo_no','工单编号'],['product_name','产品名称'],['line_name','生产线'],['status','状态'],['completion_rate','完成进度'],['planned_end','计划结束']] },
  materials: { title: '物料台账', path: '/erp/materials', id: 'material_code', icon: Boxes, cols: [['material_code','物料编码'],['name','物料名称'],['category','分类'],['available_stock','可用库存'],['safety_stock','安全库存'],['warehouse','仓库'],['supplier_name','供应商']] },
  lines: { title: '生产线', path: '/mes/production-lines', id: 'line_code', icon: Factory, cols: [['line_code','产线编码'],['name','产线名称'],['workshop','车间'],['status','状态'],['daily_capacity','日产能'],['active_alarms','未恢复报警'],['supervisor','负责人']] },
  alarms: { title: '设备报警', path: '/mes/equipment/alarms', id: 'alarm_id', icon: BellRing, cols: [['alarm_id','报警编号'],['equipment_name','设备名称'],['line_code','产线'],['alarm_level','级别'],['alarm_type','故障类型'],['start_time','发生时间'],['is_active','恢复状态']] },
} satisfies Record<Kind,{ title:string; path:string; id:string; icon:unknown; cols:Field[] }>
const route = useRoute()
const kind = computed(() => route.name as Kind)
const cfg = computed(() => config[kind.value])
const initial = () => ({ text:'', option:'', active:false })
const draft = reactive(initial()), applied = ref(initial())
const page = ref(1), size = ref(10), rows = ref<Row[]>([]), total = ref(0)
const loading = ref(false), error = ref(''), validation = ref(''), categories = ref<string[]>([])
const drawer = ref(false), detail = ref<Row|null>(null), selected = ref<Row>({}), detailLoading = ref(false), detailError = ref('')
let listVersion = 0, detailVersion = 0
const options = computed(() => kind.value === 'orders' ? ['未完成','待执行','生产中','已完成','已延期','暂停'] : kind.value === 'materials' ? categories.value : ['提示','一般','严重'])
const hint = computed(() => ({ orders:'工单号，如 WO-20260801-001',materials:'物料编码或名称',lines:'产线编码、名称或车间',alarms:'设备编码，如 EQ-L01-01' })[kind.value])
function submit(reset = false) {
  if (reset) Object.assign(draft, initial())
  const text = draft.text.trim().toUpperCase()
  validation.value = ''
  if (text && kind.value === 'orders' && !/^WO-\d{8}-\d{3}$/.test(text)) validation.value = '请输入完整工单号，格式为 WO-YYYYMMDD-三位序号。'
  if (text && kind.value === 'alarms' && !/^EQ-L\d{2}-\d{2}$/.test(text)) validation.value = '请输入完整设备编码，例如 EQ-L01-01。'
  if (validation.value) return
  applied.value = { ...draft, text: ['orders','alarms'].includes(kind.value) ? text : draft.text.trim() }
  page.value = 1
  void load()
}
async function load() {
  const version = ++listVersion, k = kind.value, f = applied.value
  loading.value = true; error.value = ''
  const params: Record<string,unknown> = { page:page.value, page_size:size.value }
  if (k === 'materials') Object.assign(params,{ category:f.option || undefined, keyword:f.text || undefined })
  if (k === 'orders') Object.assign(params,{ status:f.option || undefined, wo_nos:f.text || undefined })
  if (k === 'alarms') Object.assign(params,{ level:f.option || undefined, active_only:f.active, equipment_code:f.text || undefined })
  try {
    const { data } = await api.get(cfg.value.path,{ params:k === 'lines' ? {} : params })
    // 快速翻页或切换业务时，过期响应不能覆盖当前列表。
    if (version !== listVersion) return
    if (k === 'lines') {
      const matches = (data as Row[]).filter(r => ['line_code','name','workshop'].some(key => String(r[key]).toLowerCase().includes(f.text.toLowerCase())))
      total.value = matches.length
      rows.value = matches.slice((page.value-1)*size.value,page.value*size.value)
    } else { rows.value = data.items; total.value = data.total }
    if (!rows.value.length && total.value && page.value > 1) { page.value = Math.ceil(total.value / size.value); void load() }
  } catch { if (version === listVersion) { rows.value = []; total.value = 0; error.value = `${config[k].title}加载失败，请检查网络或服务后重试。` } }
  finally { if (version === listVersion) loading.value = false }
}
function turn(n:number) { page.value = n; void load() }
async function openDetail(row:Row) {
  const version = ++detailVersion
  selected.value = row; drawer.value = true; detailError.value = ''; detail.value = null; detailLoading.value = false
  if (kind.value === 'lines' || kind.value === 'alarms') { detail.value = row; return }
  detailLoading.value = true
  try {
    const { data } = await api.get(`${cfg.value.path}/${encodeURIComponent(String(row[cfg.value.id]))}`)
    if (version === detailVersion) detail.value = data
  } catch { if (version === detailVersion) detailError.value = '详情加载失败，请重试。' }
  finally { if (version === detailVersion) detailLoading.value = false }
}
watch(kind, async k => {
  drawer.value = false; ++detailVersion; ++listVersion
  if (!config[k]) return
  size.value = 10; submit(true)
  if (k === 'materials') {
    try { categories.value = (await api.get('/erp/materials/categories')).data }
    catch { categories.value = [] } // 仍可手工输入分类进行查询。
  }
},{ immediate:true })
const extra: Record<Kind,Field[]> = {
  orders:[['product_code','产品编码'],['priority','优先级'],['planned_qty','计划数量'],['completed_qty','完成数量'],['planned_start','计划开始'],['remark','备注']],
  materials:[['spec','规格'],['unit','计量单位'],['unit_price','单价'],['current_stock','现存量'],['reserved_stock','预留量']],
  lines:[['running_work_orders','生产中工单']], alarms:[['equipment_code','设备编码'],['wo_no','关联工单'],['end_time','恢复时间'],['duration_min','持续分钟'],['description','故障说明']],
}
type Section = { key:string; title:string; cols:Field[] }
const sections: Record<Kind,Section[]> = {
  orders:[{key:'materials',title:'工单物料需求',cols:[['material_name','物料名称'],['material_code','编码'],['required_qty','需求量'],['issued_qty','已发料'],['pending_qty','待发料'],['unit','单位']]},{key:'plans',title:'生产计划',cols:[['plan_date','日期'],['shift','班次'],['planned_qty','计划产量'],['actual_qty','实际产量']]},{key:'alarms',title:'关联设备报警',cols:[['equipment_name','设备'],['alarm_level','级别'],['description','故障说明'],['is_active','恢复状态']]}],
  materials:[{key:'supplier',title:'供应商信息',cols:[['name','供应商名称'],['supplier_code','编码'],['contact','联系人'],['phone','电话'],['lead_time_days','交期（天）'],['address','地址']]},{key:'open_purchase_orders',title:'未完成采购单',cols:[['po_no','单号'],['pending_qty','待到货'],['expected_date','预计到货'],['status','状态']]},{key:'recent_transactions',title:'最近库存变动',cols:[['txn_time','时间'],['txn_type','类型'],['quantity','数量'],['balance_after','结存']]}],
  lines:[{key:'equipment',title:'产线设备',cols:[['equipment_code','设备编码'],['name','设备名称'],['type','设备类型'],['status','设备状态']]}], alarms:[],
}
function related(key:string):Row[] { const v = detail.value?.[key]; return Array.isArray(v) ? v : v && typeof v === 'object' ? [v as Row] : [] }
function format(row:Row,key:string) {
  const v = row[key]
  if (key === 'is_active') return v ? '未恢复' : '已恢复'
  if (Array.isArray(v)) return v.join('、') || '无'
  if (v == null || v === '') return '—'
  if (key === 'completion_rate') return `${v}%`
  if (typeof v === 'number') return v.toLocaleString('zh-CN',{maximumFractionDigits:4})
  return String(v).replace(/^(\d{4}-\d\d-\d\d)T(\d\d:\d\d).*/, '$1 $2')
}
function tone(value:string) { return /未恢复|严重|延期|故障/.test(value) ? 'danger' : /生产中|完成|运行|已恢复/.test(value) ? 'good' : /暂停|一般|维护/.test(value) ? 'warn' : 'neutral' }
</script>

<template>
  <section class="ledger" :aria-label="cfg.title">
    <div class="cap"><div class="cap-title"><component :is="cfg.icon" :size="20"/><h2>{{ cfg.title }}清单</h2></div><el-button text :disabled="loading" @click="load"><RotateCw :size="15"/>刷新</el-button></div>
    <form class="filters" @submit.prevent="submit()">
      <el-input v-model="draft.text" class="keyword" :placeholder="hint" :aria-label="hint" :maxlength="50" clearable @clear="submit()"><template #prefix><Search :size="16"/></template></el-input>
      <el-select v-if="kind !== 'lines'" v-model="draft.option" class="choice" :aria-label="kind === 'orders' ? '工单状态' : kind === 'materials' ? '物料分类' : '报警级别'" :placeholder="kind === 'orders' ? '全部状态' : kind === 'materials' ? '全部分类' : '全部级别'" clearable :filterable="kind==='materials'" :allow-create="kind==='materials'" @change="submit()"><el-option v-for="o in options" :key="o" :label="o" :value="o"/></el-select>
      <el-checkbox v-if="kind === 'alarms'" v-model="draft.active" @change="submit()">仅未恢复</el-checkbox>
      <el-button native-type="submit" type="primary">查询</el-button><el-button text @click="submit(true)">重置</el-button>
    </form>
    <p v-if="validation" class="validation" role="alert">{{ validation }}</p>
    <div v-if="loading || error || !rows.length" class="state" role="status"><Inbox v-if="!loading" :size="26"/><strong>{{ loading ? '正在加载'+cfg.title+'…' : error || '没有符合条件的记录' }}</strong><el-button v-if="error" @click="load">重新加载</el-button><el-button v-else-if="!loading && (applied.text || applied.option || applied.active)" @click="submit(true)">清除筛选</el-button></div>
    <div v-else class="scroll" tabindex="0" :aria-label="cfg.title+'表格'"><table class="records"><thead><tr><th v-for="[key,label] in cfg.cols" :key="key">{{ label }}</th></tr></thead><tbody><tr v-for="r in rows" :key="String(r[cfg.id])"><td v-for="[key] in cfg.cols" :key="key">
      <button v-if="key===cfg.id" class="record-link" @click="openDetail(r)">{{ r[key] }}</button>
      <template v-else-if="key==='completion_rate'"><div class="progress"><progress :value="Number(r[key])" max="100" aria-label="工单完成率"/>{{ format(r,key) }}</div><small>{{ format(r,'completed_qty') }} / {{ format(r,'planned_qty') }}</small></template>
      <span v-else-if="['status','is_active','alarm_level'].includes(key)" class="pill" :class="tone(format(r,key))">{{ format(r,key) }}</span>
      <template v-else><span :class="{'low': key==='active_alarms' && Number(r[key])>0 || key==='available_stock' && Number(r[key]) < Number(r.safety_stock)}">{{ format(r,key) }}</span><small v-if="['available_stock','safety_stock'].includes(key)" class="unit">{{ r.unit }}</small></template>
    </td></tr></tbody></table></div>
    <footer v-if="!error && !loading"><span>共 {{ total.toLocaleString() }} 条记录</span><el-pagination layout="prev, pager, next" :page-size="size" :current-page="page" :total="total" :pager-count="5" @current-change="turn"/></footer>
  </section>
  <el-drawer v-model="drawer" :title="cfg.title+'详情'" size="min(680px, 100vw)" append-to-body>
    <section class="detail"><h2>{{ selected[cfg.id] }}</h2><div v-if="detailLoading || detailError" class="state" role="status">{{ detailLoading ? '正在读取详情…' : detailError }}<el-button v-if="detailError" @click="openDetail(selected)">重试</el-button></div>
      <template v-if="detail"><dl class="facts"><template v-for="[key,label] in [...cfg.cols,...extra[kind]].filter(c=>c[0]!==cfg.id)" :key="key"><div><dt>{{ label }}</dt><dd>{{ format(detail,key) }}</dd></div></template></dl>
        <section v-for="s in sections[kind]" :key="s.key" class="related"><h3>{{ s.title }}</h3><p v-if="!related(s.key).length">暂无{{ s.title }}记录</p><dl v-else-if="s.key==='supplier'" class="facts"><div v-for="[key,label] in s.cols" :key="key"><dt>{{ label }}</dt><dd>{{ format(related(s.key)[0]!,key) }}</dd></div></dl><div v-else class="scroll" tabindex="0" :aria-label="s.title"><table><thead><tr><th v-for="[key,label] in s.cols" :key="key">{{ label }}</th></tr></thead><tbody><tr v-for="(r,i) in related(s.key)" :key="i"><td v-for="[key] in s.cols" :key="key">{{ format(r,key) }}</td></tr></tbody></table></div></section>
      </template>
    </section>
  </el-drawer>
</template>

<style scoped>
.ledger,.detail{color:#203550;font-variant-numeric:tabular-nums;--blue:#245eb4;--rule:#dee6ef}.ledger{min-width:0;max-width:100%;overflow:hidden;border:1px solid var(--rule);border-radius:10px;background:white}.cap,.filters,footer,.cap-title,.progress{display:flex;align-items:center}.cap,footer{justify-content:space-between;padding:17px 22px}.cap{border-bottom:1px solid var(--rule)}.cap-title{gap:10px;color:var(--blue)}h2,h3,p,dl,dd{margin:0}.cap h2{font-size:16px;color:#203550}.cap :deep(.el-button span){gap:6px}.filters{gap:10px;flex-wrap:wrap;padding:17px 22px}.filters .el-button+.el-button{margin-left:0}.keyword{width:265px}.choice{width:144px}.scroll{overflow-x:auto}.scroll:focus-visible,.record-link:focus-visible{outline:2px solid var(--blue);outline-offset:-2px}table{width:100%;border-collapse:collapse;text-align:left;font-size:13px;line-height:1.55}th,td{white-space:nowrap;padding:13px 14px;border-bottom:1px solid #e7edf4}th{background:#f2f6fb;color:#51657e;font-size:12px;font-weight:600}.records td:first-child,.records th:first-child{padding-left:22px}.records tbody tr:hover{background:#f7faff}.record-link{border:0;background:none;color:var(--blue);font:inherit;font-weight:650;cursor:pointer;padding:3px 0}.record-link:hover{text-decoration:underline}.pill{display:inline-flex;align-items:center;gap:6px;border-radius:4px;padding:2px 8px;font-size:12px}.pill::before{content:'';width:5px;height:5px;border-radius:100%;background:currentColor}.danger{color:#ac3737;background:#fff0ef}.good{color:#146951;background:#e6f5ef}.warn,.low{color:#965507}.warn{background:#fff2d9}.neutral{color:#46678d;background:#eaf1f9}.progress{gap:8px;font-weight:600}.progress progress{width:54px;height:6px;accent-color:var(--blue)}small,footer,.related p{color:#5d7087}.unit{margin-left:3px}footer{font-size:12px;gap:8px;flex-wrap:wrap}.state{min-height:180px;display:grid;align-content:center;justify-items:center;gap:14px;background:#fafcfe;color:#526984;text-align:center;padding:16px}.validation{margin:0 22px 12px;color:#a83939;font-size:13px}.detail h2{color:var(--blue);font-size:22px;margin-bottom:18px;overflow-wrap:anywhere}.facts{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px 18px;background:#f4f7fb;border-radius:6px;padding:17px}.facts dt{font-size:12px;color:#526984}.facts dd{font-size:14px;margin-top:3px;overflow-wrap:anywhere}.related{margin-top:25px}.related h3{border-left:3px solid var(--blue);padding-left:9px;font-size:15px;margin-bottom:12px}.related p{font-size:13px}.related td,.related th{padding:9px}.detail .state{min-height:140px}@media(max-width:650px){.filters,.cap,footer{padding:13px}.keyword{width:100%}.choice{width:126px}.filters{gap:8px}.records td:first-child,.records th:first-child{padding-left:13px}footer{justify-content:center}.detail .facts{gap:13px;padding:12px}}
</style>
