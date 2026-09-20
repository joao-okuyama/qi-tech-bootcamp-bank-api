from sqlalchemy import Column, DateTime, Integer, String, func

from models.base import Base


class StatusTransferencia(Base):
    __tablename__ = "status_transferencia"

    id = Column(Integer, primary_key=True)
    codigo = Column(String(30), nullable=False)
    criado_em = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
