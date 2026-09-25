from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, func

from models.base import Base


class DesignacaoAprovador(Base):
    __tablename__ = "designacao_aprovador"

    id = Column(BigInteger, primary_key=True)
    organizacao_cliente_id = Column(BigInteger, ForeignKey("organizacao_estudantil.cliente_id"), nullable=False)
    aluno_cliente_id = Column(BigInteger, ForeignKey("aluno.cliente_id"), nullable=False)
    inicio_vigencia = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    fim_vigencia = Column(DateTime(timezone=True))
