from sqlalchemy.exc import IntegrityError

from controllers.base_controller import BaseController
from controllers.access_policy import AccessPolicy
from errors.payment_errors import BankingAccessDenied
from dtos.account_dto import AccountDTO
from errors import InvalidParameter
from errors.banking_errors import (
    BankingEntityNotFound, BankingRegistrationConflict, CustomerCannotOpenAccount,
)
from repositories.account_repository import AccountRepository
from repositories.customer_repository import CustomerRepository
from utils.banking_validation import parse_key


MAX_STATEMENT_OFFSET = 10_000


class AccountController(BaseController):
    def __init__(self):
        super().__init__(self.__class__.__name__)
        self.repository = AccountRepository(self.context)
        self.customer_repository = CustomerRepository(self.context)
        self.access = AccessPolicy(self.context)

    def create(self, customer_key: str) -> dict:
        self.access.require_internal()
        # O cliente é o bloqueio comum às duas tentativas de abrir sua primeira conta.
        customer = self.customer_repository.get_by_key(parse_key(customer_key), for_update=True)
        if customer is None:
            raise BankingEntityNotFound("customer")
        if customer.status.codigo != "ATIVO" or self.customer_repository.get_registration(customer) is None:
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
            if getattr(getattr(error.orig, "diag", None), "constraint_name", None) == "unico_conta_cliente":
                raise BankingRegistrationConflict("customer account") from None
            raise

    def get_by_key(self, account_key: str) -> dict:
        return AccountDTO.obj_to_dict(self._get_account(account_key))

    def get_balance(self, account_key: str) -> dict:
        return AccountDTO.balance_to_dict(self._get_account(account_key))

    def statement(self, account_key, limit, page=0, cursor=None):
        offset = page * limit
        if cursor is None and offset > MAX_STATEMENT_OFFSET:
            raise InvalidParameter(f"The statement offset must not exceed {MAX_STATEMENT_OFFSET}.")
        account = self._get_account(account_key)
        if cursor is not None:
            movement = self.repository.movement_cursor(account.id, parse_key(cursor))
            if movement is None:
                raise InvalidParameter("The cursor does not belong to this account.")
            rows = self.repository.list_after_cursor(account.id, movement, limit)
        else:
            rows = self.repository.list_movements(account.id, limit, offset)
        return AccountDTO.statement(rows, limit, page=None if cursor else page, cursor=cursor)

    def _get_account(self, key: str):
        account = self.repository.get_by_key(parse_key(key))
        if account is None:
            raise BankingEntityNotFound("account")
        if account.cliente_id is None:
            raise BankingAccessDenied()
        self.access.require_customer(account.cliente_id)
        return account
