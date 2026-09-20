from sqlalchemy import BigInteger, Column, DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID

from models.base import Base


class Universidade(Base):
    __tablename__ = "universidade"

    id = Column(BigInteger, primary_key=True)
    chave = Column(UUID(as_uuid=True), nullable=False, server_default=func.gen_random_uuid())
    nome = Column(String(255), nullable=False)
    criado_em = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
