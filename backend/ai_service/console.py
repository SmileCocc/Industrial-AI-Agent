"""控制台只读网关。业务库仅通过 ERP/MES 的已知 HTTP 路由访问。"""
import asyncio
from collections import deque
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
import re
from time import monotonic
from urllib.parse import urlsplit

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from ai_service import history
from ai_service.agent.llm import clean
from ai_service.agent.settings import AgentError, get_agent_settings
from ai_service.tools import TOOLS, schemas
from ai_service.tools.operations import operations, totals
from ai_service.tools.shortage import ToolError, gather_limited, pages
from common.auth import get_current_user
from common.db import check_db

router = APIRouter(prefix='/api', dependencies=[Depends(get_current_user)])
# 路径和查询键分别校验，不转发客户端的请求头、任意地址或重定向。
PAGE = 'page page_size '
ROUTES = {
    'ERP': {
        'materials': PAGE+'category keyword', 'materials/categories': '', r'materials/MAT-[0-9]{4}': '',
        'inventory': PAGE+'codes category', 'inventory/low-stock': PAGE,
        'inventory/transactions': PAGE+'material_code start_date end_date', 'suppliers': PAGE+'codes keyword',
        'purchase-orders': PAGE+'material_codes supplier_code status'},
    'MES': {
        'work-orders': PAGE+'status line_code start_date end_date wo_nos', 'work-orders/materials': 'wo_nos',
        r'work-orders/WO-[0-9]{8}-[0-9]{3}': '', r'work-orders/WO-[0-9]{8}-[0-9]{3}/materials': '',
        'production-plans': PAGE+'plan_date start_date end_date line_code wo_no', 'production-lines': 'line_code',
        'equipment/alarms': PAGE+'start_date end_date line_code level wo_no equipment_code active_only'}}
recent = deque(maxlen=1000)


def allowed(system, path):
    return next((keys.split() for pattern, keys in ROUTES.get(system, {}).items() if re.fullmatch(pattern, path)), None)


def settings():
    try:
        return get_agent_settings()
    except AgentError:
        raise HTTPException(503, '服务配置无效') from None


def origin(value):
    try:
        url = urlsplit(value)
        if url.scheme in ('http', 'https') and url.hostname and not (url.username or url.password):
            host = f'[{url.hostname}]' if ':' in url.hostname else url.hostname
            return f'{url.scheme}://{host}' + (f':{url.port}' if url.port else '')
    except ValueError:
        pass
    return None


@asynccontextmanager
async def reader(owner, source):
    s = settings()
    token = s.service_token.get_secret_value()
    async with httpx.AsyncClient(timeout=s.http_timeout, trust_env=False, follow_redirects=False,
                                 headers={'X-Service-Token': token} if token else {}) as client:
        async def get(system, path, params):
            base = {'ERP': s.erp_base_url, 'MES': s.mes_base_url}[system]
            if not origin(base) or urlsplit(base).query or urlsplit(base).fragment:
                raise HTTPException(503, '业务服务地址配置无效')
            endpoint = '/health' if source == 'health' else '/api'+path
            start = monotonic()
            event = dict(timestamp=datetime.now().astimezone().isoformat(), source=source, system=system,
                         method='GET', path=endpoint, status='error', status_code=None, tool_name=None)
            try:
                response = await client.get(base.rstrip('/')+endpoint, params=params)
                code = event['status_code'] = response.status_code
                if code != 200:
                    raise HTTPException(code if code in (404, 422, 429, 503, 504) else 502,
                                        f'{system} 查询失败')
                data = response.json()
                if not isinstance(data, (list, dict)):
                    raise ValueError()
                if source == 'health' and not (isinstance(data, dict) and data.get('status') == 'ok'
                                               and data.get('database_ok') is True):
                    raise HTTPException(503, f'{system} 未就绪')
                event['status'] = 'success'
                return clean(data, s) if source == 'gateway' else data
            except httpx.TimeoutException:
                event['status'] = 'timeout'
                raise HTTPException(504, f'{system} 请求超时') from None
            except (httpx.HTTPError, ValueError):
                raise HTTPException(502, f'{system} 服务或响应异常') from None
            finally:
                event['duration_ms'] = round((monotonic()-start)*1000)
                recent.append((owner, event))
        yield get


async def gateway(system, path, request, owner):
    keys = allowed(system, path)
    if keys is None:
        raise HTTPException(404, '业务接口不存在')
    params = request.query_params
    if set(params).difference(keys) or len(params.multi_items()) != len(params) or any(len(v)>2000 for v in params.values()):
        raise HTTPException(422, '业务查询参数无效')
    async with reader(owner, 'gateway') as get:
        return await get(system, '/'+path, dict(params))


@router.get('/erp/{path:path}')
async def erp(path: str, request: Request, user=Depends(get_current_user)):
    return await gateway('ERP', path, request, user['user_id'])


@router.get('/mes/{path:path}')
async def mes(path: str, request: Request, user=Depends(get_current_user)):
    return await gateway('MES', path, request, user['user_id'])


@router.get('/dashboard')
async def dashboard(user=Depends(get_current_user)):
    async with reader(user['user_id'], 'dashboard') as get:
        try:
            days = [(date.today() - timedelta(days=i)).isoformat() for i in reversed(range(7))]
            # 五项指标互不依赖，并行获取；否则刷新一次要串行等待数十次业务请求。
            eff, stock, pending, plans, categories = await gather_limited([
                operations(get, 'efficiency'),
                get('ERP', '/inventory/low-stock', {'page_size': 1}),
                get('MES', '/work-orders', {'status': '待执行', 'page_size': 1}),
                pages(get, 'MES', '/production-plans', {'start_date': days[0], 'end_date': days[-1]}),
                get('ERP', '/materials/categories', {})], 5)
            trend = [dict(date=day, **totals([p for p in plans if p['plan_date'] == day])) for day in days]
            counts = await gather_limited([get('ERP', '/inventory', {'category': category, 'page_size': 1})
                                           for category in categories], 5)
            distribution = [dict(category=category, count=inv['total']) for category, inv in zip(categories, counts)]
            return clean(dict(date=eff['date'], lines=eff['lines'], trend=trend, inventory_distribution=distribution,
                         metrics=dict(**eff['total'], low_stock_count=stock['total'], shortage_order_count=len(eff['shortages']),
                         pending_order_count=pending['total'], today_alarm_count=sum(r['alarms_started_today'] for r in eff['lines']),
                         delayed_order_count=len(eff['delayed_orders']), active_alarm_count=len(eff['active_alarms']))), settings())
        except (ToolError, KeyError, ValueError, TypeError):
            raise HTTPException(502, '业务数据不完整，无法计算驾驶舱指标') from None


@router.get('/system/integrations')
async def integrations(user=Depends(get_current_user)):
    s = settings()
    async with reader(user['user_id'], 'health') as get:
        async def check(system, base):
            start = monotonic()
            if system == 'AI':
                ok = await run_in_threadpool(check_db, history.engine)
            else:
                try:
                    await get(system, '/health', {})
                    ok = True
                except HTTPException:
                    ok = False
            return dict(system=system, base_url=base, status='ok' if ok else 'degraded',
                        duration_ms=round((monotonic()-start)*1000))
        return clean({'items': await asyncio.gather(check('AI', '/'), check('ERP', origin(s.erp_base_url)),
                                                    check('MES', origin(s.mes_base_url)))}, s)


@router.get('/system/model-config')
def model_config():
    s = settings()
    return clean(dict(provider=s.model_provider, model=s.model_name, base_url=origin(s.model_base_url),
                      api_key_configured=bool(s.model_api_key.get_secret_value().strip()), temperature=s.model_temperature,
                      max_tokens=s.model_max_tokens, timeout=s.model_timeout), s)


def events(owner):
    # 仅扫描当前用户的轨迹，按写入顺序倒序、分批读取；不将问题、参数、模型回复或原始错误传出。
    query = select(history.Turn.result).join(history.Conversation).where(history.Conversation.owner == owner).order_by(
        history.Turn.id.desc()).execution_options(yield_per=20)
    with Session(history.engine) as db:
        for result in db.scalars(query):
            for event in reversed(result.get('trace', [])):
                if event.get('type') == 'tool_call' and event.get('tool_name') in TOOLS:
                    yield event


@router.get('/system/call-logs')
def call_logs(limit: int = Query(50, ge=1, le=200), user=Depends(get_current_user)):
    owner = user['user_id']
    rows = [event for uid, event in recent.copy() if uid == owner]
    count = 0
    for e in events(owner):
        path = e.get('path', '')
        if (e.get('method') == 'GET' and path.startswith('/api/') and
                allowed(e.get('system'), path[5:]) is not None):
            rows.append({k: e.get(k) for k in ('timestamp', 'system', 'method', 'path', 'status', 'status_code',
                                                'duration_ms', 'tool_name')} | {'source': 'tool'})
            count += 1
            if count >= limit:
                break
    return clean({'items': sorted(rows, key=lambda e: e['timestamp'], reverse=True)[:limit]}, settings())


def tool_catalog(owner):
    last = {}
    for e in events(owner):
        if not e.get('method'):
            last.setdefault(e['tool_name'], e)
        if len(last) == len(TOOLS):
            break
    items = []
    for schema in schemas():
        item = schema['function']
        name = item['name']
        event = last.get(name, {})
        items.append(dict(**item, system=TOOLS[name][1], last_called_at=event.get('timestamp'),
                          last_status=event.get('status')))
    return items
