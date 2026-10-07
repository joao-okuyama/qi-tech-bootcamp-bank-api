from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID

from models.base import Base


class Cliente(Base):
    __tablename__ = "cliente"

    id = Column(BigInteger, primary_key=True)
    chave = Column(UUID(as_uuid=True), nullable=False, server_default=func.gen_random_uuid())
    tipo = Column(String(30), nullable=False)
    status_id = Column(Integer, ForeignKey("status_cliente.id"), nullable=False, server_default="1")
    status = relationship("StatusCliente", lazy="selectin")
    criado_em = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
