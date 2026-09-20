from sqlalchemy import BigInteger, CHAR, Column, DateTime, ForeignKey, String, func

from models.base import Base


class OrganizacaoEstudantil(Base):
    __tablename__ = "organizacao_estudantil"

    cliente_id = Column(BigInteger, ForeignKey("cliente.id"), primary_key=True)
    universidade_id = Column(BigInteger, ForeignKey("universidade.id"), nullable=False)
    razao_social = Column(String(255), nullable=False)
    nome_fantasia = Column(String(255), nullable=False)
    cnpj = Column(CHAR(14), nullable=False)
    criado_em = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
