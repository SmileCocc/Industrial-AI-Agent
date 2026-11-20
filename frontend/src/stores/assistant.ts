import { defineStore } from 'pinia'
import { ref } from 'vue'
import { isAxiosError } from 'axios'
import { api } from '../api'

export interface HistoryItem { id: string; title: string; updated_at: string }
interface Report { total?: { planned: number; actual: number; rate_pct: number | null }; count?: number; alarm_count?: number }
export interface Turn {
  question: string; answer?: string; detail?: string; duration_ms?: number
  analysis_data?: Record<string, Report>; shortage_data?: { total: number; shortage_order_count: number } | null
  trace?: { seq: number; summary: string; tool_name?: string; system?: string; status: string; duration_ms?: number; arguments?: unknown; error?: string }[]
}
export const useAssistantStore = defineStore('assistant', () => {
  const history = ref<HistoryItem[]>([]), id = ref<string | null>(null), turns = ref<Turn[]>([])
  const draft = ref(''), sending = ref(false), loading = ref(false), listing = ref(false)
  const listError = ref(''), detailError = ref(''), more = ref(false), started = ref(0)
  let page = 0, listVersion = 0, detailVersion = 0

  async function list(next = false) {
    if (next && (listing.value || !more.value)) return
    const version = ++listVersion, target = next ? page + 1 : 1
    listing.value = true; listError.value = ''
    try {
      const { data } = await api.get<HistoryItem[]>('/agent/conversations', { params: { page: target, page_size: 30 } })
      if (version !== listVersion) return
      history.value = next ? [...new Map([...history.value, ...data].map(row => [row.id, row])).values()] : data
      page = target; more.value = data.length === 30
    } catch { if (version === listVersion) listError.value = '历史会话加载失败' }
    finally { if (version === listVersion) listing.value = false }
  }
  function fresh() {
    if (sending.value) return
    detailVersion++; id.value = null; turns.value = []; draft.value = ''; detailError.value = ''; loading.value = false
  }
  async function open(cid: string) {
    if (sending.value) return
    const version = ++detailVersion
    id.value = cid; turns.value = []; loading.value = true; detailError.value = ''; draft.value = ''
    try {
      const { data } = await api.get<{ turns: Turn[] }>(`/agent/conversations/${cid}`)
      if (version === detailVersion) turns.value = data.turns
    } catch { if (version === detailVersion) detailError.value = '无法读取这段会话，请重新加载。' }
    finally { if (version === detailVersion) loading.value = false }
  }
  async function send() {
    const question = draft.value.trim()
    if (!question || question.length > 4000 || sending.value || loading.value || detailError.value) return
    sending.value = true; started.value = Date.now(); draft.value = ''
    turns.value.push({ question })
    let result: Partial<Turn>
    try {
      const { data } = await api.post<Turn & {conversation_id: string}>('/agent/chat', { message: question, conversation_id: id.value }, { timeout: 0 })
      id.value = data.conversation_id; result = data
    } catch (error) {
      const body = isAxiosError(error) ? error.response?.data : undefined
      // 业务错误也可能已入库；保留服务端会话 ID，后续追问接回原会话。
      if (typeof body?.conversation_id === 'string') id.value = body.conversation_id
      result = { detail: typeof body?.detail === 'string' ? body.detail : '未收到完整回答。请先刷新历史确认是否已保存，再决定是否重试。', trace: Array.isArray(body?.trace) ? body.trace : [] }
    }
    turns.value[turns.value.length - 1] = { ...result, question }
    sending.value = false; void list()
  }
  return { history, id, turns, draft, sending, loading, listing, listError, detailError, more, started, list, fresh, open, send }
})
