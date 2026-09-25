from sqlalchemy.exc import IntegrityError

from controllers.access_policy import AccessPolicy
from controllers.base_controller import BaseController
from dtos.university_dto import UniversityDTO
from errors.banking_errors import BankingEntityNotFound, BankingRegistrationConflict
from repositories.university_repository import UniversityRepository
from utils.banking_validation import clean_registration_text, parse_key


class UniversityController(BaseController):
    def __init__(self):
        super().__init__(self.__class__.__name__)
        self.repository = UniversityRepository(self.context)
        self.access = AccessPolicy(self.context)

    def create(self, payload: dict) -> dict:
        self.access.require_internal()
        name = clean_registration_text(payload["name"], "name")
        try:
            university = self.repository.create(name)
            result = UniversityDTO.obj_to_dict(university)
            self.session.commit()
            return result
        except IntegrityError as error:
            self.session.rollback()
            if getattr(getattr(error.orig, "diag", None), "constraint_name", None) == "unico_universidade_nome":
                raise BankingRegistrationConflict("university name") from None
            raise

    def get_by_key(self, university_key: str) -> dict:
        self.access.require_internal()
        university = self.repository.get_by_key(parse_key(university_key))
        if university is None:
            raise BankingEntityNotFound("university")
        return UniversityDTO.obj_to_dict(university)
