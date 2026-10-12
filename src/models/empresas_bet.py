from sqlalchemy import CHAR, Column, Integer, String

from models.base import Base


class EmpresaBetAutorizada(Base):
    __tablename__ = "empresas_bet_autorizadas"

    id = Column(Integer, primary_key=True)
    cnpj = Column(CHAR(14), nullable=False, unique=True)
    razao_social = Column(String(255), nullable=False)
