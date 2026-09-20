from sqlalchemy import BigInteger, CHAR, Column, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID

from models.base import Base


class Conta(Base):
    __tablename__ = "conta"

    id = Column(BigInteger, primary_key=True)
    chave = Column(UUID(as_uuid=True), nullable=False, server_default=func.gen_random_uuid())
    cliente_id = Column(BigInteger, ForeignKey("cliente.id"), nullable=False)
    saldo_centavos = Column(BigInteger, nullable=False, server_default="0")
    moeda = Column(CHAR(3), nullable=False, server_default="BRL")
    situacao = Column(String(20), nullable=False, server_default="ATIVA")
    criado_em = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
