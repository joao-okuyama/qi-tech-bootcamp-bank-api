from sqlalchemy import Column, Integer, String

from models.base import Base


class StatusConta(Base):
    __tablename__ = "status_conta"

    id = Column(Integer, primary_key=True)
    codigo = Column(String(20), nullable=False, unique=True)
