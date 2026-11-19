"""日志：控制台 + 按服务写文件；统一对密钥做脱敏。"""
import logging
import re
import time
from logging.handlers import RotatingFileHandler

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from common.config import BACKEND_DIR, get_settings

# 匹配常见密钥形式：sk-xxx、Bearer xxx、api_key=xxx、password=xxx
_SECRET_PATTERNS = [
    (re.compile(r"sk-[A-Za-z0-9_\-]{8,}"), "sk-****"),
    (re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._\-]+"), r"\1****"),
    (re.compile(r"(?i)((?:api[_-]?key|password|token)[\"']?\s*[:=]\s*[\"']?)[^\s,\"'&]+"), r"\1****"),
]


def redact(text: str) -> str:
    for pattern, repl in _SECRET_PATTERNS:
        text = pattern.sub(repl, text)
    return text


class RedactingFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return redact(super().format(record))


def setup_logging(service: str) -> logging.Logger:
    log_dir = BACKEND_DIR / "logs"
    log_dir.mkdir(exist_ok=True)
    fmt = RedactingFormatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
    file_handler = RotatingFileHandler(log_dir / f"{service}.log", maxBytes=5_000_000, backupCount=3, encoding="utf-8")
    console = logging.StreamHandler()
    for h in (file_handler, console):
        h.setFormatter(fmt)
    root = logging.getLogger()
    root.handlers = [file_handler, console]
    root.setLevel(get_settings().log_level.upper())
    return logging.getLogger(service)


def install_middleware(app: FastAPI, logger: logging.Logger) -> None:
    """记录每个请求的方法、路径、状态码、耗时；未捕获异常统一记录堆栈并返回 500。"""

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            logger.exception("未处理异常 %s %s", request.method, request.url.path)
            response = JSONResponse(status_code=500, content={"detail": "服务内部错误", "code": "INTERNAL_ERROR"})
        cost = (time.perf_counter() - start) * 1000
        logger.info("%s %s?%s -> %s %.1fms", request.method, request.url.path, request.url.query, response.status_code, cost)
        return response
