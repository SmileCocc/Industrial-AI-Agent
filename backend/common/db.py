"""数据库工具：每个服务只创建自己库的引擎，不跨库访问。"""
import re
from collections.abc import Callable, Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from common.config import get_settings

_DB_NAME_RE = re.compile(r"^[A-Za-z0-9_]{1,64}$")


def make_engine(db_name: str) -> Engine:
    return create_engine(get_settings().mysql_url(db_name), pool_pre_ping=True, pool_recycle=3600)


def ensure_database(db_name: str) -> None:
    """库不存在时创建。库名需拼接进 DDL，因此先做白名单校验。"""
    if not _DB_NAME_RE.match(db_name):
        raise ValueError(f"非法数据库名: {db_name}")
    engine = create_engine(get_settings().mysql_url(None))
    with engine.begin() as conn:
        conn.execute(text(f"CREATE DATABASE IF NOT EXISTS `{db_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci"))
    engine.dispose()


def session_dependency(factory: sessionmaker) -> Callable[[], Iterator[Session]]:
    def get_db() -> Iterator[Session]:
        with factory() as db:
            yield db
    return get_db


def check_db(engine: Engine) -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
