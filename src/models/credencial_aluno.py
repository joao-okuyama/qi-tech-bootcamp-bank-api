from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, String, func

from models.base import Base


class CredencialAluno(Base):
    __tablename__ = "credencial_aluno"

    aluno_cliente_id = Column(BigInteger, ForeignKey("aluno.cliente_id"), primary_key=True)
    resumo_token = Column(String(64), nullable=False)
    criado_em = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
