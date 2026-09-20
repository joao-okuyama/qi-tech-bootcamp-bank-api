from sqlalchemy import BigInteger, Column, DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID

from models.base import Base


class Cliente(Base):
    __tablename__ = "cliente"

    id = Column(BigInteger, primary_key=True)
    chave = Column(UUID(as_uuid=True), nullable=False, server_default=func.gen_random_uuid())
    tipo = Column(String(30), nullable=False)
    situacao = Column(String(20), nullable=False, server_default="ATIVO")
    criado_em = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
