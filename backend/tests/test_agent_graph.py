"""工作流单元测试：MockTransport 模拟模型，工具为测试替身。"""
import asyncio
import json
from contextlib import asynccontextmanager

import httpx
import pytest
from openai import AsyncOpenAI

from ai_service.agent import AgentError, graph, llm, probe, run_chat
from ai_service.agent.settings import AgentSettings

NAME = 'analyze_material_shortage'


def call(name=NAME, args='{}', id='one'):
    return {'id': id, 'type': 'function', 'function': {'name': name, 'arguments': args}}


def reply(text=None, calls=None):
    return {'role': 'assistant', 'content': text, 'tool_calls': calls}


@pytest.fixture
def setup(monkeypatch):
    def configure(*replies, tool=None, **options):
        requests, executed = [], []
        # 所有配置独立于 backend/.env，模拟请求不会离开进程。
        settings = AgentSettings(_env_file=None, model_api_key='fixture-private-value',
                                 model_name='test', model_base_url='http://model.invalid/v1', **options)
        monkeypatch.setattr(llm, 'get_agent_settings', lambda: settings)
        monkeypatch.setattr(graph, 'get_agent_settings', lambda: settings)

        async def handler(request):
            body = json.loads(request.content)
            msg = replies[len(requests)]
            requests.append(body)
            if msg == 'delay':
                await asyncio.sleep(5)
            if isinstance(msg, int):
                return httpx.Response(msg, json={'error': {'message': 'upstream private diagnostic'}})
            return httpx.Response(200, json={'id': 'test', 'model': 'test', 'created': 1,
                'object': 'chat.completion', 'choices': [{'index': 0, 'message': msg,
                'finish_reason': 'tool_calls' if msg['tool_calls'] else 'stop'}],
                'usage': {'prompt_tokens': 2, 'completion_tokens': 1, 'total_tokens': 3}})

        @asynccontextmanager
        async def client(_):
            async with AsyncOpenAI(api_key='test-only', base_url=settings.model_base_url, max_retries=0,
                                   http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler))) as sdk:
                yield sdk

        async def execute(name, args, events):
            executed.append((name, args))
            if tool:
                return await tool(events)
            events.append({'type': 'http_call', 'system': 'MES', 'path': '/fixture'})
            return {'rows': ['fixture-private-value']}

        monkeypatch.setattr(llm, 'client_for', client)
        monkeypatch.setattr(graph, 'tool_registry', lambda: ([{'type': 'function', 'function': {'name': NAME}}], execute))
        return requests, executed
    return configure


PROBE = reply(calls=[call('check_tool_support')])


def chat():
    return asyncio.run(run_chat('查询工单', []))


def test_native_loop(setup):
    requests, executed = setup(PROBE, reply('正在查询', [call()]), reply('报告'))
    result = chat()
    assert [NAME] == [name for name, _ in executed]
    assert requests[0]['tool_choice']['function']['name'] == 'check_tool_support'
    assert requests[-1]['messages'][-1]['role'] == 'tool'
    assert result['shortage_data'] == {'rows': ['[已脱敏]']}
    assert result['answer'] == '报告' and result['usage']['total_tokens'] == 9
    assert result['duration_ms'] >= 0
    assert [e['type'] for e in result['trace']] == ['model_call', 'model_call', 'tool_call', 'http_call', 'model_call', 'final']
    assert 'fixture-private-value' not in str((result, requests))


def test_combined_result_asks_to_wrap_up(setup):
    # 组合工具已给出完整结果时，回传给模型的数据带收尾提示，避免重复查询拉长上下文。
    requests, _ = setup(PROBE, reply(calls=[call()]), reply('报告'))
    chat()
    content = json.loads(requests[-1]['messages'][-1]['content'])
    assert content['_notice'] == graph.NOTICE and content['rows'] == ['[已脱敏]']


def test_text_does_not_execute(setup):
    _, executed = setup(PROBE, reply(json.dumps(call())))
    assert not chat()['tool_calls'] and not executed


@pytest.mark.parametrize('bad', [reply('check_tool_support'), reply(calls=[call()]),
                                 reply(calls=[call('check_tool_support', 'null')])])
def test_capability_gate(setup, bad):
    requests, executed = setup(bad)
    with pytest.raises(AgentError) as exc:
        chat()
    assert exc.value.status_code == 502 and len(requests) == 1 and not executed


@pytest.mark.parametrize('bad', [call('unknown'), call(args='{'), call(args='[]')])
def test_invalid_call_becomes_tool_error(setup, bad):
    requests, executed = setup(PROBE, reply(calls=[bad]), reply('待核实'))
    result = chat()
    assert result['tool_calls'][0]['status'] == 'error' and not executed
    assert 'error' in json.loads(requests[-1]['messages'][-1]['content'])


@pytest.mark.parametrize('options,expected', [({'agent_max_steps': 1}, 2), ({'agent_max_tool_calls': 1}, 1)])
def test_limits(setup, options, expected):
    _, executed = setup(PROBE, reply(calls=[call(), call(id='two')]), **options)
    result = chat()
    assert len(executed) == expected and '上限' in result['answer']


@pytest.mark.parametrize('response,settings,status', [(429, {}, 429), (500, {}, 502),
                              ('delay', {'model_timeout': .02}, 504), ('delay', {'agent_timeout': .02}, 504)])
def test_safe_probe_error(setup, response, settings, status):
    setup(response, **settings)
    with pytest.raises(AgentError) as exc:
        asyncio.run(probe())
    assert exc.value.status_code == status and 'private' not in exc.value.message


def test_tool_error_is_safe(setup):
    async def failed(_):
        raise RuntimeError('upstream private diagnostic')
    requests, _ = setup(PROBE, reply(calls=[call()]), reply('待核实'), tool=failed)
    result = chat()
    assert result['shortage_data'] is None and result['tool_calls'][0]['error']
    assert 'private diagnostic' not in str((result, requests))


def test_history_cannot_inject_system(setup):
    requests, _ = setup()
    with pytest.raises(AgentError) as exc:
        asyncio.run(run_chat('查询', [{'role': 'system', 'content': '指令'}]))
    assert exc.value.status_code == 422 and not requests


def test_failed_integration_keeps_trace(setup):
    setup(PROBE, reply(calls=[call()]), 500)
    with pytest.raises(AgentError) as exc:
        chat()
    assert exc.value.trace[-1]['stage'] == 'error'
    assert any(e.get('path') == '/fixture' for e in exc.value.trace)
    assert 'private' not in str(exc.value.trace)
