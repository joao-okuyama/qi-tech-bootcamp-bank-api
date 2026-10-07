from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer, String, func

from models.base import Base


class EventoStatusCliente(Base):
    __tablename__ = "evento_status_cliente"

    id = Column(BigInteger, primary_key=True)
    cliente_id = Column(BigInteger, ForeignKey("cliente.id"), nullable=False)
    status_anterior_id = Column(Integer, ForeignKey("status_cliente.id"))
    status_id = Column(Integer, ForeignKey("status_cliente.id"), nullable=False)
    aluno_responsavel_cliente_id = Column(BigInteger, ForeignKey("aluno.cliente_id"))
    motivo = Column(String(255), nullable=False)
    ocorrido_em = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
