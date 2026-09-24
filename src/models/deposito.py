from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID

from models.base import Base


class Deposito(Base):
    __tablename__ = "deposito"
    id = Column(BigInteger, primary_key=True)
    chave = Column(UUID(as_uuid=True), nullable=False, server_default=func.gen_random_uuid())
    conta_id = Column(BigInteger, ForeignKey("conta.id"), nullable=False)
    referencia = Column(String(255), nullable=False)
    valor_centavos = Column(BigInteger, nullable=False)
    criado_em = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
