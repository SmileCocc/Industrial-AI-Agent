"""统一配置：全部来自环境变量 / backend/.env，代码中不写死任何地址、密钥或模型名。"""
from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", env_file_encoding="utf-8", extra="ignore")

    # MySQL
    mysql_host: str = "127.0.0.1"
    mysql_port: int = 3306
    mysql_user: str = "root"
    mysql_password: SecretStr = SecretStr("")
    erp_db_name: str = "industrial_erp"
    mes_db_name: str = "industrial_mes"
    agent_db_name: str = "industrial_agent"

    # 服务地址与服务间调用
    erp_base_url: str = "http://127.0.0.1:8001"
    mes_base_url: str = "http://127.0.0.1:8002"
    service_token: SecretStr = SecretStr("")
    http_timeout: float = 10

    log_level: str = "INFO"

    def mysql_url(self, database: str | None = None) -> URL:
        # URL.create 会正确转义密码中的特殊字符
        return URL.create(
            "mysql+pymysql",
            username=self.mysql_user,
            password=self.mysql_password.get_secret_value(),
            host=self.mysql_host,
            port=self.mysql_port,
            database=database,
            query={"charset": "utf8mb4"},
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
