from sqlalchemy import BigInteger, CHAR, Column, Date, DateTime, ForeignKey, String, func

from models.base import Base


class Aluno(Base):
    __tablename__ = "aluno"

    cliente_id = Column(BigInteger, ForeignKey("cliente.id"), primary_key=True)
    universidade_id = Column(BigInteger, ForeignKey("universidade.id"), nullable=False)
    nome_completo = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False)
    cpf = Column(CHAR(11), nullable=False)
    data_nascimento = Column(Date, nullable=False)
    criado_em = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
