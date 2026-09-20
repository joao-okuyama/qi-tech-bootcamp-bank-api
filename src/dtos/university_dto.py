from models import Universidade


class UniversityDTO:
    @staticmethod
    def obj_to_dict(university: Universidade) -> dict:
        return {
            "university_key": str(university.chave),
            "name": university.nome,
            "created_at": university.criado_em.isoformat(),
        }
