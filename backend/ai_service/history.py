"""对话记录只保存在 Agent 自己的库。模型请求期间不占用数据库连接。"""
from datetime import datetime
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from common.config import get_settings
from common.db import ensure_database, make_engine

settings = get_settings()
engine = make_engine(settings.agent_db_name)


class Base(DeclarativeBase):
    pass


class Conversation(Base):
    __tablename__ = 'conversations'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    owner: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(String(100))
    updated_at: Mapped[datetime] = mapped_column(DateTime)


class Turn(Base):
    __tablename__ = 'conversation_turns'
    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey('conversations.id'), index=True)
    question: Mapped[str] = mapped_column(Text)
    result: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


def initialize():
    if settings.agent_db_name in (settings.erp_db_name, settings.mes_db_name):
        raise RuntimeError('Agent 必须配置独立数据库')
    ensure_database(settings.agent_db_name)
    Base.metadata.create_all(engine)


def owned(db, cid, owner):
    row = db.get(Conversation, cid)
    if not row or row.owner != owner:
        raise HTTPException(404, '对话不存在')
    return row


def recent_messages(cid, owner):
    if cid is None:
        return []
    with Session(engine) as db:
        owned(db, cid, owner)
        turns = db.scalars(select(Turn).where(Turn.conversation_id == cid).order_by(Turn.id.desc()).limit(5)).all()
        history = []
        for turn in reversed(turns):
            if 'answer' in turn.result:
                history.extend([{'role': 'user', 'content': turn.question},
                                {'role': 'assistant', 'content': turn.result['answer'][:4000]}])
        return history


def save_turn(cid, owner, question, result):
    with Session(engine) as db, db.begin():
        if cid is None:
            cid = str(uuid4())
            row = Conversation(id=cid, owner=owner, title=question[:80])
            db.add(row)
        else:
            row = owned(db, cid, owner)
        row.updated_at = datetime.now()
        db.flush()
        db.add(Turn(conversation_id=cid, question=question, result=result))
    return cid


def list_conversations(owner, page, size):
    with Session(engine) as db:
        rows = db.scalars(select(Conversation).where(Conversation.owner == owner).order_by(
            Conversation.updated_at.desc(), Conversation.id).offset((page-1)*size).limit(size))
        return [{'id': r.id, 'title': r.title, 'updated_at': r.updated_at} for r in rows]


def detail(cid, owner):
    with Session(engine) as db:
        row = owned(db, cid, owner)
        turns = db.scalars(select(Turn).where(Turn.conversation_id == cid).order_by(Turn.id))
        return {'id': cid, 'title': row.title, 'turns': [
            {'question': t.question, 'created_at': t.created_at, **t.result} for t in turns]}
