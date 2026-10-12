from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID

from models.base import Base


class Transferencia(Base):
    __tablename__ = "transferencia"

    id = Column(BigInteger, primary_key=True)
    chave = Column(UUID(as_uuid=True), nullable=False, server_default=func.gen_random_uuid())
    conta_origem_id = Column(BigInteger, ForeignKey("conta.id"), nullable=False)
    conta_destino_id = Column(BigInteger, ForeignKey("conta.id"), nullable=False)
    aluno_solicitante_cliente_id = Column(BigInteger, ForeignKey("aluno.cliente_id"), nullable=False)
    aluno_aprovador_cliente_id = Column(BigInteger, ForeignKey("aluno.cliente_id"))
    valor_centavos = Column(BigInteger, nullable=False)
    tarifa_centavos = Column(BigInteger, nullable=False, server_default="0")
    tipo = Column(String(10), nullable=False)
    descricao = Column(String(255))
    status_id = Column(Integer, ForeignKey("status_transferencia.id"), nullable=False)
    chave_idempotencia = Column(String(255), nullable=False)
    criado_em = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    concluido_em = Column(DateTime(timezone=True))
