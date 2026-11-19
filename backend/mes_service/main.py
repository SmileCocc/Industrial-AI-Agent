"""模拟 MES 服务（端口 8002）。启动：uvicorn mes_service.main:app --port 8002"""
from fastapi import FastAPI

from common.config import get_settings
from common.db import check_db
from common.logging_setup import install_middleware, setup_logging
from mes_service.api.routes import router
from mes_service.database import engine

logger = setup_logging("mes_service")
app = FastAPI(title="模拟 MES 服务", version="0.1.0")
install_middleware(app, logger)
app.include_router(router)


@app.get("/health", tags=["system"])
def health():
    db_ok = check_db(engine)
    return {"service": "mes", "status": "ok" if db_ok else "degraded",
            "database": get_settings().mes_db_name, "database_ok": db_ok}
