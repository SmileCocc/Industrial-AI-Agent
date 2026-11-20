"""工业 Agent 服务，仅对话与执行轨迹使用本地 MySQL。"""
import logging
import time
from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool

from ai_service import history
from ai_service.agent import AgentError, probe, run_chat
from ai_service.console import router as console_router, tool_catalog
from common.auth import get_current_user
from common.db import check_db
from common.logging_setup import setup_logging

logger = setup_logging('ai_service')
# SDK 的 HTTP 调试输出可能带有模型地址或鉴权信息。
for name in ('httpx', 'httpcore', 'openai'):
    logging.getLogger(name).setLevel(logging.WARNING)


@asynccontextmanager
async def lifespan(app):
    await run_in_threadpool(history.initialize)
    yield
    history.engine.dispose()


app = FastAPI(title='Industrial AI Agent', version='0.3', lifespan=lifespan)
app.include_router(console_router)


@app.middleware('http')
async def access_log(request: Request, call_next):
    start = time.monotonic()
    try:
        response = await call_next(request)
    except Exception as exc:
        # 只记录异常类型，不将 SQL 参数、模型响应或请求正文写入日志。
        logger.error('请求失败 %s', type(exc).__name__)
        response = JSONResponse({'detail': '服务内部错误'}, status_code=500)
    logger.info('%s %s %s %.0fms', request.method, request.scope.get('route', '').path
                if request.scope.get('route') else '(unknown)', response.status_code, (time.monotonic()-start)*1000)
    return response


class ChatInput(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: UUID | None = None


@app.get('/health')
def health():
    ok = check_db(history.engine)
    return JSONResponse({'service': 'ai', 'status': 'ok' if ok else 'degraded', 'database_ok': ok},
                        status_code=200 if ok else 503)


@app.post('/api/system/model-test')
async def model_test(user=Depends(get_current_user)):
    try:
        return await probe()
    except AgentError as exc:
        logger.warning('模型探测失败 %s', exc.status_code)
        raise HTTPException(exc.status_code, exc.message) from None


@app.get('/api/agent/tools')
def tools(user=Depends(get_current_user)):
    return tool_catalog(user['user_id'])


@app.post('/api/agent/chat')
async def chat(body: ChatInput, user=Depends(get_current_user)):
    cid = str(body.conversation_id) if body.conversation_id else None
    owner = user['user_id']
    past = await run_in_threadpool(history.recent_messages, cid, owner)
    try:
        result = await run_chat(body.message, past)
        status = 200
    except AgentError as exc:
        status = exc.status_code
        result = {'detail': exc.message, 'trace': getattr(exc, 'trace', [])}
    cid = await run_in_threadpool(history.save_turn, cid, owner, body.message, result)
    return JSONResponse({'conversation_id': cid, **result}, status_code=status)


@app.get('/api/agent/conversations')
def conversations(page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=100), user=Depends(get_current_user)):
    return history.list_conversations(user['user_id'], page, page_size)


@app.get('/api/agent/conversations/{cid}')
def conversation(cid: UUID, user=Depends(get_current_user)):
    return history.detail(str(cid), user['user_id'])
