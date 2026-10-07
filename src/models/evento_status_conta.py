from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer, String, func

from models.base import Base


class EventoStatusConta(Base):
    __tablename__ = "evento_status_conta"

    id = Column(BigInteger, primary_key=True)
    conta_id = Column(BigInteger, ForeignKey("conta.id"), nullable=False)
    status_anterior_id = Column(Integer, ForeignKey("status_conta.id"))
    status_id = Column(Integer, ForeignKey("status_conta.id"), nullable=False)
    aluno_responsavel_cliente_id = Column(BigInteger, ForeignKey("aluno.cliente_id"))
    motivo = Column(String(255), nullable=False)
    ocorrido_em = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
