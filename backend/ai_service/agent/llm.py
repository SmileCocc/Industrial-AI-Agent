"""OpenAI 兼容客户端与原生工具能力探测。上游错误可能含凭据，不透传。"""
import asyncio
import json
import re
from contextlib import asynccontextmanager
from time import monotonic
from urllib.parse import urlsplit

import httpx
from openai import APIError, APITimeoutError, AsyncOpenAI, RateLimitError

from .settings import AgentError, AgentSettings, get_agent_settings


def elapsed(start):
    return int((monotonic() - start) * 1000)


def clean(value, settings):
    secrets = [v.get_secret_value() for v in
               (settings.model_api_key, settings.service_token, settings.mysql_password)]

    def redact(obj):
        if isinstance(obj, str):
            for s in sorted(filter(None, secrets), key=len, reverse=True):
                obj = obj.replace(s, '[已脱敏]')
            return re.sub(r'(?i)\b(?:Bearer\s+[^\s,;"\']+|sk-[\w-]+)', '[已脱敏]', obj)
        if isinstance(obj, list):
            return [redact(v) for v in obj]
        if isinstance(obj, dict):
            return {redact(k): redact(v) for k, v in obj.items()}
        return obj

    return redact(value)


@asynccontextmanager
async def client_for(s: AgentSettings):
    key = s.model_api_key.get_secret_value()
    url = urlsplit(s.model_base_url)
    if (s.model_provider != 'openai_compatible' or url.scheme not in {'https', 'http'} or
            not url.hostname or url.username or url.password or url.query or url.fragment or
            not s.model_name.strip() or not key.strip()):
        raise AgentError(503, '请配置 OpenAI 兼容模型的地址、名称和密钥')
    async with AsyncOpenAI(api_key=key, base_url=s.model_base_url, max_retries=0,
                           http_client=httpx.AsyncClient(trust_env=False), timeout=s.model_timeout) as client:
        yield client


async def completion(client, s, **kwargs):
    try:
        async with asyncio.timeout(s.model_timeout):
            response = await client.chat.completions.create(model=s.model_name, **kwargs)
    except (APITimeoutError, TimeoutError):
        raise AgentError(504, '模型请求超时') from None
    except RateLimitError:
        raise AgentError(429, '模型服务限流') from None
    except APIError:
        raise AgentError(502, '模型服务请求失败，请检查网关和模型配置') from None
    if not response.choices or not response.choices[0].message:
        raise AgentError(502, '模型返回空响应')
    choice = response.choices[0]
    if choice.finish_reason in {'length', 'content_filter'}:
        raise AgentError(502, '模型未生成完整响应')
    return choice.message, response.usage


async def check(client, s):
    name = 'check_tool_support'
    fn = {'name': name, 'parameters': {'type': 'object', 'properties': {}, 'additionalProperties': False}}
    msg, usage = await completion(client, s, messages=[{'role': 'user', 'content': '请调用探测工具。'}],
                                  tools=[{'type': 'function', 'function': fn}],
                                  tool_choice={'type': 'function', 'function': {'name': name}})
    calls = msg.tool_calls or []
    if len(calls) == 1 and calls[0].type == 'function' and calls[0].id and calls[0].function.name == name:
        try:
            if json.loads(calls[0].function.arguments) == {}:
                return usage
        except (ValueError, TypeError):
            pass
    raise AgentError(502, '模型未返回有效的原生工具调用，能力探测失败')


async def probe() -> dict:
    s = get_agent_settings()
    start = monotonic()
    try:
        async with asyncio.timeout(s.agent_timeout), client_for(s) as client:
            await check(client, s)
        return clean(dict(ok=True, supports_tool_calls=True, model=s.model_name, duration_ms=elapsed(start)), s)
    except AgentError:
        raise
    except TimeoutError:
        raise AgentError(504, '模型探测超时') from None
    except Exception:
        raise AgentError(502, '模型探测失败') from None
