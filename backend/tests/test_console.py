"""离线覆盖控制台入口，不启动应用生命周期或连接业务数据库。"""
from contextlib import asynccontextmanager
from datetime import date

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from ai_service import console, history
from ai_service.agent.settings import AgentSettings
from ai_service.main import app
from common.auth import get_current_user


@pytest.fixture
def api(monkeypatch):
    s = AgentSettings(_env_file=None, service_token=SecretStr('secret-for-test'),
                      model_api_key=SecretStr('dummy-model-key'), model_base_url='https://example.test/v1?hidden=key')
    monkeypatch.setattr(console, 'settings', lambda: s)
    app.dependency_overrides[get_current_user] = lambda: {'user_id': 'test-owner'}
    console.recent.clear()
    yield TestClient(app)
    app.dependency_overrides.pop(get_current_user)
    console.recent.clear()


def test_gateway_and_health(api, monkeypatch):
    def handler(req):
        assert req.headers['X-Service-Token'] == 'secret-for-test'
        if req.url.path == '/api/materials':
            assert dict(req.url.params) == {'page': '2'}
            return httpx.Response(200, json={'items': ['secret-for-test'], 'total': 12})
        if req.url.path == '/api/inventory':
            return httpx.Response(422, json={'detail': 'private-response'})
        if req.url.path == '/health':
            return httpx.Response(200, json={'status': 'degraded', 'database_ok': False})
        raise httpx.ReadTimeout('private-response')

    client = httpx.AsyncClient
    monkeypatch.setattr(console.httpx, 'AsyncClient', lambda **kw: client(transport=httpx.MockTransport(handler), **kw))
    monkeypatch.setattr(console, 'check_db', lambda _: True)
    assert api.get('/api/erp/materials?page=2').json() == {'items': ['[已脱敏]'], 'total': 12}
    assert api.post('/api/erp/materials').status_code == 405
    assert api.get('/api/erp/health').status_code == 404
    assert api.get('/api/erp/materials?url=other').status_code == 422
    assert api.get('/api/mes/work-orders').status_code == 504
    bad = api.get('/api/erp/inventory')
    assert bad.status_code == 422 and 'private-response' not in bad.text
    assert [r['status'] for r in api.get('/api/system/integrations').json()['items']] == ['ok', 'degraded', 'degraded']
    cfg = api.get('/api/system/model-config')
    assert cfg.json()['base_url'] == 'https://example.test' and cfg.json()['api_key_configured']
    assert 'dummy-model-key' not in cfg.text


def test_historical_http_and_tool_status(api, monkeypatch):
    db = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    monkeypatch.setattr(history, 'engine', db)
    history.Base.metadata.create_all(db)
    name = 'query_material_inventory'
    ev = dict(type='tool_call', tool_name=name, status='success', timestamp='2026-01-02T10:00:00+08:00')
    child = dict(ev, method='GET', system='ERP', path='/api/inventory', status_code=200, duration_ms=8,
                 arguments={'keyword': 'private-text'})
    history.save_turn(None, 'test-owner', 'private-text', {'trace': [ev, child]})
    history.save_turn(None, 'other', 'other-user', {'trace': [dict(child, path='/api/suppliers')]})
    response = api.get('/api/system/call-logs')
    assert 'private-text' not in response.text
    rows = response.json()['items']
    assert len(rows) == 1 and rows[0]['path'] == '/api/inventory' and rows[0]['source'] == 'tool'
    catalog = {r['name']: r for r in api.get('/api/agent/tools').json()}
    assert catalog[name]['last_status'] == 'success' and catalog[name]['last_called_at'] == ev['timestamp']
    assert catalog['analyze_operations']['last_status'] is None
    db.dispose()


def test_dashboard_real_aggregation(api, monkeypatch):
    day = date.today().isoformat()

    @asynccontextmanager
    async def fake_reader(owner, source):
        async def get(system, path, params):
            if path == '/production-lines':
                return [{'line_code': 'L01', 'name': '一线'}]
            if path == '/materials/categories':
                return ['铸件']
            if params.get('page_size') == 1:
                return {'total': 13}
            rows = []
            if path == '/production-plans' and params.get('plan_date', day) == day:
                rows = [{'plan_date': day, 'line_code': 'L01', 'planned_qty': 20, 'actual_qty': 15}]
            return {'total': len(rows), 'items': rows, 'page': 1}
        yield get

    monkeypatch.setattr(console, 'reader', fake_reader)
    data = api.get('/api/dashboard').json()
    assert data['metrics']['rate_pct'] == 75 and data['metrics']['pending_order_count'] == 13
    assert data['metrics']['shortage_order_count'] == 0
    assert len(data['trend']) == 7 and data['trend'][0]['rate_pct'] is None and data['trend'][-1]['actual'] == 15
    assert data['inventory_distribution'] == [{'category': '铸件', 'count': 13}]
