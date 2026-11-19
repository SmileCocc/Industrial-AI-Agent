"""模拟 ERP 服务（端口 8001）。启动：uvicorn erp_service.main:app --port 8001"""
from fastapi import FastAPI

from common.config import get_settings
from common.db import check_db
from common.logging_setup import install_middleware, setup_logging
from erp_service.api.routes import router
from erp_service.database import engine

logger = setup_logging("erp_service")
app = FastAPI(title="模拟 ERP 服务", version="0.1.0")
install_middleware(app, logger)
app.include_router(router)


@app.get("/health", tags=["system"])
def health():
    db_ok = check_db(engine)
    return {"service": "erp", "status": "ok" if db_ok else "degraded",
            "database": get_settings().erp_db_name, "database_ok": db_ok}
