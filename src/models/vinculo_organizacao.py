from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, String, func

from models.base import Base


class VinculoOrganizacao(Base):
    __tablename__ = "vinculo_organizacao"

    id = Column(BigInteger, primary_key=True)
    organizacao_cliente_id = Column(BigInteger, ForeignKey("organizacao_estudantil.cliente_id"), nullable=False)
    aluno_cliente_id = Column(BigInteger, ForeignKey("aluno.cliente_id"), nullable=False)
    papel = Column(String(20), nullable=False)
    inicio_vigencia = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    fim_vigencia = Column(DateTime(timezone=True))
