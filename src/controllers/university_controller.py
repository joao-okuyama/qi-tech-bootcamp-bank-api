from sqlalchemy.exc import IntegrityError

from controllers.base_controller import BaseController
from dtos.university_dto import UniversityDTO
from errors.banking_errors import BankingEntityNotFound, BankingRegistrationConflict
from repositories.university_repository import UniversityRepository
from utils.banking_validation import parse_key


class UniversityController(BaseController):
    def __init__(self):
        super().__init__(self.__class__.__name__)
        self.repository = UniversityRepository(self.context)

    def create(self, payload: dict) -> dict:
        try:
            university = self.repository.create(payload["name"].strip())
            result = UniversityDTO.obj_to_dict(university)
            self.session.commit()
            return result
        except IntegrityError as error:
            self.session.rollback()
            if getattr(error.orig.diag, "constraint_name", None) == "unico_universidade_nome":
                raise BankingRegistrationConflict("university name") from None
            raise

    def get_by_key(self, university_key: str) -> dict:
        university = self.repository.get_by_key(parse_key(university_key))
        if university is None:
            raise BankingEntityNotFound("university")
        return UniversityDTO.obj_to_dict(university)
