"""鉴权预留位。第一版：服务间令牌（可选）+ 固定演示用户。"""
import secrets

from fastapi import Header, HTTPException

from common.config import get_settings


def verify_service_token(x_service_token: str | None = Header(default=None)) -> None:
    """SERVICE_TOKEN 非空时，ERP/MES 要求调用方携带 X-Service-Token。"""
    expected = get_settings().service_token.get_secret_value()
    if expected and not secrets.compare_digest(x_service_token or "", expected):
        raise HTTPException(status_code=401, detail="服务令牌无效")


def get_current_user() -> dict:
    # TODO: 接入 JWT / SSO 后在此解析用户与权限
    return {"user_id": "demo", "name": "演示用户", "roles": ["viewer"]}
