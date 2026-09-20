from sqlalchemy.exc import IntegrityError

from controllers.base_controller import BaseController
from dtos.account_dto import AccountDTO
from errors.banking_errors import (
    BankingEntityNotFound, BankingRegistrationConflict, CustomerCannotOpenAccount,
)
from repositories.account_repository import AccountRepository
from repositories.customer_repository import CustomerRepository
from utils.banking_validation import parse_key


class AccountController(BaseController):
    def __init__(self):
        super().__init__(self.__class__.__name__)
        self.repository = AccountRepository(self.context)
        self.customer_repository = CustomerRepository(self.context)

    def create(self, customer_key: str) -> dict:
        # O cliente é o bloqueio comum às duas tentativas de abrir sua primeira conta.
        customer = self.customer_repository.get_by_key(parse_key(customer_key), for_update=True)
        if customer is None:
            raise BankingEntityNotFound("customer")
        if customer.situacao != "ATIVO" or self.customer_repository.get_registration(customer) is None:
            raise CustomerCannotOpenAccount()
        if self.repository.get_by_customer_id(customer.id) is not None:
            raise BankingRegistrationConflict("customer account")
        try:
            account = self.repository.create(customer.id)
            result = AccountDTO.obj_to_dict(account)
            self.session.commit()
            return result
        except IntegrityError as error:
            self.session.rollback()
            if getattr(error.orig.diag, "constraint_name", None) == "unico_conta_cliente":
                raise BankingRegistrationConflict("customer account") from None
            raise

    def get_by_key(self, account_key: str) -> dict:
        return AccountDTO.obj_to_dict(self._get_account(account_key))

    def get_balance(self, account_key: str) -> dict:
        return AccountDTO.balance_to_dict(self._get_account(account_key))

    def get_statement(self, account_key: str, limit: int, offset: int) -> dict:
        account = self._get_account(account_key)
        rows = self.repository.list_movements(account.id, limit, offset)
        return {
            "data": [AccountDTO.movement_to_dict(*row) for row in rows[:limit]],
            "is_last_page": len(rows) <= limit,
        }

    def _get_account(self, key: str):
        account = self.repository.get_by_key(parse_key(key))
        if account is None:
            raise BankingEntityNotFound("account")
        return account
