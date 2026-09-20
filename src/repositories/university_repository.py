from database import Context
from models import Universidade


class UniversityRepository:
    def __init__(self, context: Context):
        self.session = context.db_session

    def create(self, name: str) -> Universidade:
        university = Universidade(nome=name)
        self.session.add(university)
        self.session.flush()
        return university

    def get_by_key(self, key) -> Universidade:
        return self.session.query(Universidade).filter(Universidade.chave == key).first()
