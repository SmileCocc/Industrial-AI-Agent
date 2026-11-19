from sqlalchemy.orm import sessionmaker

from common.config import get_settings
from common.db import make_engine, session_dependency

engine = make_engine(get_settings().erp_db_name)
SessionLocal = sessionmaker(engine, expire_on_commit=False)
get_db = session_dependency(SessionLocal)
