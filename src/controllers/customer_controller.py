from sqlalchemy.exc import IntegrityError

from controllers.base_controller import BaseController
from controllers.access_policy import AccessPolicy
from dtos.customer_dto import CustomerDTO
from errors.banking_errors import (
    BankingEntityNotFound, BankingRegistrationConflict, InvalidBankingRegistration,
)
from repositories.customer_repository import CustomerRepository
from repositories.university_repository import UniversityRepository
from utils.banking_validation import clean_registration_text, is_valid_cnpj, parse_key, validate_birthdate, validate_cpf


class CustomerController(BaseController):
    def __init__(self):
        super().__init__(self.__class__.__name__)
        self.repository = CustomerRepository(self.context)
        self.university_repository = UniversityRepository(self.context)
        self.access = AccessPolicy(self.context)

    def create_student(self, payload: dict) -> dict:
        self.access.require_internal()
        payload = dict(payload)
        payload["full_name"] = clean_registration_text(payload["full_name"], "full_name")
        payload["email"] = clean_registration_text(payload["email"].lower(), "email")
        validate_cpf(payload["cpf"])
        birthdate = validate_birthdate(payload["birthdate"])
        university = self._get_university(payload["university_key"])
        try:
            customer = self.repository.create_student(payload, university.id, birthdate)
            result = CustomerDTO.obj_to_dict(customer)
            self.session.commit()
            return result
        except IntegrityError as error:
            self.session.rollback()
            self._raise_registration_conflict(error)
            raise

    def create_organization(self, payload: dict) -> dict:
        self.access.require_internal()
        payload = dict(payload)
        for field in ("legal_name", "trade_name"):
            payload[field] = clean_registration_text(payload[field], field)
        payload["email"] = clean_registration_text(payload["email"].lower(), "email")
        if not is_valid_cnpj(payload["cnpj"]):
            raise InvalidBankingRegistration("The CNPJ check digits are invalid.")
        university = self._get_university(payload["university_key"])
        try:
            customer = self.repository.create_organization(payload, university.id)
            result = CustomerDTO.obj_to_dict(customer)
            self.session.commit()
            return result
        except IntegrityError as error:
            self.session.rollback()
            self._raise_registration_conflict(error)
            raise

    def get_by_key(self, customer_key: str) -> dict:
        customer = self.repository.get_by_key(parse_key(customer_key))
        if customer is None:
            raise BankingEntityNotFound("customer")
        self.access.require_customer(customer.id)
        return CustomerDTO.obj_to_dict(customer)

    def _get_university(self, key: str):
        university = self.university_repository.get_by_key(parse_key(key))
        if university is None:
            raise BankingEntityNotFound("university")
        return university

    @staticmethod
    def _raise_registration_conflict(error: IntegrityError) -> None:
        fields = {
            "unico_aluno_cpf": "CPF",
            "unico_aluno_email": "email",
            "unico_organizacao_cnpj": "CNPJ",
        }
        field = fields.get(getattr(getattr(error.orig, "diag", None), "constraint_name", None))
        if field is not None:
            raise BankingRegistrationConflict(field) from None
