from sqlalchemy import CHAR, Column, DateTime, Integer

from models.base import Base


class SincronizacaoEmpresasBet(Base):
    __tablename__ = "sincronizacao_empresas_bet"

    id = Column(Integer, primary_key=True)
    atualizado_em = Column(DateTime(timezone=True))
    resumo_conteudo = Column(CHAR(64))
    quantidade = Column(Integer, nullable=False, server_default="0")
