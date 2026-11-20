"""使用项目种子数据和 HTTPX MockTransport，无需数据库、服务或 .env。"""
import asyncio
import json
from types import SimpleNamespace

import httpx
import pytest
from pydantic import SecretStr

from ai_service import tools
from ai_service.tools.shortage import allocate
from seed.generate import build


def transport(monkeypatch, handler):
    monkeypatch.setattr(tools, 'get_settings', lambda: SimpleNamespace(
        erp_base_url='http://erp', mes_base_url='http://mes', http_timeout=2,
        service_token=SecretStr('test-only-token')))
    client = httpx.AsyncClient
    monkeypatch.setattr(tools.httpx, 'AsyncClient', lambda **kw: client(transport=httpx.MockTransport(handler), **kw))


@pytest.mark.parametrize('single', [False, True])
def test_seed_shortages(monkeypatch, single):
    db = json.loads(json.dumps(build(), default=str))
    mes, erp, ids = db['mes'], db['erp'], db['wo_no_of']
    paths = []

    def handler(request):
        assert request.method == 'GET' and request.headers['X-Service-Token'] == 'test-only-token'
        path, p = request.url.path, request.url.params
        paths.append(path)
        if path == '/api/work-orders':
            assert p['status'] == '未完成'
            rows = [w for w in mes['work_orders'] if w['status'] != '已完成']
        elif path == '/api/work-orders/materials':
            rows = [{'wo_no': no, 'materials': [dict(m, pending_qty=m['required_qty'] - m['issued_qty'])
                     for m in mes['work_order_materials'] if m['wo_no'] == no]} for no in p['wo_nos'].split(',')]
            return httpx.Response(200, json=rows)
        elif path == '/api/inventory':
            rows = [m for m in erp['materials'] if m['material_code'] in p['codes'].split(',')]
        elif path == '/api/production-plans':
            rows = [r for r in mes['production_plans'] if r['wo_no'] == p['wo_no']]
        elif path == '/api/inventory/transactions':
            rows = [r for r in erp['inventory_transactions'] if r['material_code'] == p['material_code']]
            rows.sort(key=lambda r: r['txn_time'], reverse=True)
        else:
            pytest.fail(path)
        size = int(p['page_size'])
        return httpx.Response(200, json=dict(total=len(rows), items=rows[:size], page=1, page_size=size))

    transport(monkeypatch, handler)
    events = []
    args = {'wo_nos': [ids['P3']]} if single else {}
    result = asyncio.run(tools.execute('analyze_material_shortage', args, events))
    assert [e['path'] for e in events] == paths
    assert all(e['status'] == 'success' for e in events)
    assert 'test-only-token' not in json.dumps(events)
    by_order = {w['wo_no']: w for w in result['work_orders']}
    mos = by_order[ids['P3']]['shortages'][0]
    assert (mos['material_code'], mos['shortage_pct']) == ('MAT-1002', 50)
    assert {a['wo_no'] for a in mos['prior_allocations']} == {ids[k] for k in ('R3', 'R6', 'R7')}
    assert by_order[ids['P3']]['plans']['items'][0]['wo_no'] == ids['P3']
    assert result['transactions']['MAT-1002']['items'][0]['ref_no']
    if single:
        assert result['total'] == 1
    else:
        assert result['shortage_order_count'] == 3
        assert {s['material_code']: s['shortage_pct'] for s in by_order[ids['P1']]['shortages']} == {
            'MAT-1001': 100, 'MAT-1018': 60}
        assert by_order[ids['P2']]['shortages'][0]['shortage_pct'] == 20
    json.dumps(result, allow_nan=False)


def test_priority_decimal():
    orders = [dict(wo_no=no, priority=p, status='待执行', planned_start='2026-01-01')
              for no, p in [('a', '低'), ('b', '高')]]
    demands = {w['wo_no']: [dict(material_code='x', material_name='线', unit='米', pending_qty=0.2)] for w in orders}
    result = allocate(orders, demands, {'x': {'available_stock': 0.3}}, {'a', 'b'})
    assert [w['wo_no'] for w in result] == ['b', 'a']
    assert result[0]['shortages'] == []
    assert result[1]['shortages'][0]['shortage_qty'] == 0.1


@pytest.mark.parametrize(('name', 'args'), [
    ('query_work_orders', {'start_date': '2026-01-02', 'end_date': '2026-01-01'}),
    ('query_supplier', {'page_size': 51}), ('query_supplier', {'password': 'private'}),
    ('query_work_order_materials', {'wo_nos': ['WO-20260101-001'] * 51}),
    ('query_material_detail', {'material_code': '../private'}), ('private', {})])
def test_invalid_before_http(name, args, monkeypatch):
    monkeypatch.setattr(tools, 'get_settings', lambda: pytest.fail('参数错误不应读取配置'))
    events = []
    with pytest.raises(tools.ToolError) as error:
        asyncio.run(tools.execute(name, args, events))
    assert 'private' not in str(error.value) and events == []


def test_http_failure(monkeypatch):
    assert len(tools.schemas()) == 12
    transport(monkeypatch, lambda _: httpx.Response(503, text='private'))
    events = []
    with pytest.raises(tools.ToolError) as error:
        asyncio.run(tools.execute('query_supplier', {'keyword': 'private'}, events))
    assert events[0]['status_code'] == 503 and events[0]['status'] == 'error'
    assert 'private' not in str(error.value) + json.dumps(events)
