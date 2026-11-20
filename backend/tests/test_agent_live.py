"""通过已启动的服务做第三阶段验收，显式启用后才调用收费模型。"""
import os

import httpx
import pytest


@pytest.mark.skipif(os.getenv('RUN_MAGPIE_LIVE') != '1', reason='设置 RUN_MAGPIE_LIVE=1 进行真实模型验收')
def test_magpie_shortage_roundtrip():
    with httpx.Client(base_url='http://127.0.0.1:8000', timeout=180, trust_env=False) as client:
        probe = client.post('/api/system/model-test')
        assert probe.status_code == 200, probe.text
        assert probe.json()['supports_tool_calls'] is True
        reply = client.post('/api/agent/chat', json={'message': '请做今日工单缺料分析。哪些工单缺哪些物料、差多少、会影响哪些生产计划？'})
        assert reply.status_code == 200, reply.text
        result = reply.json()
        assert result['answer'] and result['shortage_data'] is not None
        assert any(call.get('tool_name') == 'analyze_material_shortage' for call in result['tool_calls'])
        systems = {event.get('system') for event in result['trace']}
        assert {'ERP', 'MES'} <= systems
        saved = client.get('/api/agent/conversations/' + result['conversation_id'])
        assert saved.status_code == 200
        assert saved.json()['turns'][-1]['shortage_data'] == result['shortage_data']
