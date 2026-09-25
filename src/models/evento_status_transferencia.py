from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer, func

from models.base import Base


class EventoStatusTransferencia(Base):
    __tablename__ = "evento_status_transferencia"
    id = Column(BigInteger, primary_key=True)
    transferencia_id = Column(BigInteger, ForeignKey("transferencia.id"), nullable=False)
    status_id = Column(Integer, ForeignKey("status_transferencia.id"), nullable=False)
    aluno_responsavel_cliente_id = Column(BigInteger, ForeignKey("aluno.cliente_id"))
    ocorrido_em = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
