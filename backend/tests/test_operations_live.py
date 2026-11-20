"""通过自然语言入口验收四项经营分析；显式开启才访问 Magpie。"""
import os
from datetime import date, timedelta

import httpx
import pytest
from common.config import get_settings

CASES = [('plan', '今日生产计划完成率是多少？哪些产线未达目标？'),
         ('inventory', '哪些物料低于安全库存，对应供应商是谁？'),
         ('equipment', '最近一周哪些设备出现异常，对生产有什么影响？'),
         ('efficiency', '分析今天生产效率下降的可能原因，区分事实和待核实原因。')]


@pytest.mark.skipif(os.getenv('RUN_MAGPIE_LIVE') != '1', reason='需启用真实模型测试')
@pytest.mark.parametrize('scenario,question', CASES)
def test_operations(scenario, question):
    s = get_settings()
    with httpx.Client(timeout=180, trust_env=False) as c:
        r = c.post('http://127.0.0.1:8000/api/agent/chat', json={'message': question})
        assert r.status_code == 200, r.json().get('detail')
        result = r.json()
        data = result['analysis_data'][scenario]
        answer = result['answer']
        assert answer and any(e.get('method') == 'GET' and e['status'] == 'success' for e in result['trace'])
        headers = {'X-Service-Token': s.service_token.get_secret_value()}
        def rows(base, path, **params):
            r = c.get(base+'/api/'+path, params=dict(params, page_size=200), headers=headers)
            r.raise_for_status()
            return r.json()
        if scenario in ('plan', 'efficiency'):
            plans = rows(s.mes_base_url, 'production-plans', plan_date=data['date'])['items']
            assert data['total']['planned'] == sum(p['planned_qty'] for p in plans)
            assert data['total']['actual'] == sum(p['actual_qty'] for p in plans)
            assert str(data['total']['planned']) in answer.replace(',', '')
        if scenario == 'inventory':
            stock = rows(s.erp_base_url, 'inventory/low-stock')['items']
            assert {m['material_code']:m['supplier'] for m in data['materials']} == {m['material_code']:m['supplier_name'] for m in stock}
            assert all(m['material_code'] in answer for m in stock)
        if scenario == 'equipment':
            alarms = rows(s.mes_base_url, 'equipment/alarms', start_date=date.today()-timedelta(days=6), end_date=date.today())
            assert data['alarm_count'] == alarms['total']
            assert {d['code'] for d in data['devices']} == {a['equipment_code'] for a in alarms['items']}
            assert str(data['alarm_count']) in answer
        if scenario == 'efficiency':
            assert '待核实' in answer and {'ERP', 'MES'} <= {e.get('system') for e in result['trace']}
        print(scenario, result['conversation_id'], result['duration_ms'], answer[:100])
