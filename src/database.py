from contextvars import ContextVar
from typing import Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from constants import DATABASE_URL


engine = create_engine(DATABASE_URL, pool_size=5, pool_recycle=600, pool_pre_ping=True, hide_parameters=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False)


class Context:
    def __init__(self):
        self.db_session: Optional[Session] = None
        self.credential_type: Optional[str] = None
        self.credential_digest: Optional[str] = None
        self.token = None

    def get_or_create_session(self):
        if self.db_session is None:
            self.db_session = SessionLocal()
        return self.db_session


_context = ContextVar("context", default=None)


def open_context():
    # O objeto mutavel compartilha a sessao entre a rota e o middleware.
    context = Context()
    context.token = _context.set(context)
    return context


def clear_context(context=None):
    context = context or _context.get()
    if context is not None and context.token is not None:
        _context.reset(context.token)
        context.token = None


def get_context():
    context = _context.get()
    if context is None:
        raise RuntimeError("Nao existe contexto. O middleware session_manager deve abrir a requisicao.")
    return context
