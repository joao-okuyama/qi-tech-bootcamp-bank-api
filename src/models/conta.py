from sqlalchemy import BigInteger, CHAR, Column, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID

from models.base import Base


class Conta(Base):
    __tablename__ = "conta"

    id = Column(BigInteger, primary_key=True)
    chave = Column(UUID(as_uuid=True), nullable=False, server_default=func.gen_random_uuid())
    cliente_id = Column(BigInteger, ForeignKey("cliente.id"))
    finalidade = Column(String(20), nullable=False, server_default="CLIENTE")
    saldo_centavos = Column(BigInteger, nullable=False, server_default="0")
    moeda = Column(CHAR(3), nullable=False, server_default="BRL")
    status_id = Column(Integer, ForeignKey("status_conta.id"), nullable=False, server_default="1")
    status = relationship("StatusConta", lazy="selectin")
    criado_em = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
