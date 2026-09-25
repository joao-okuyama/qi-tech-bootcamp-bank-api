from datetime import datetime, timezone
from hashlib import sha256
from secrets import token_urlsafe

from controllers.access_policy import AccessPolicy
from controllers.base_controller import BaseController
from errors.banking_errors import BankingEntityNotFound
from errors.payment_errors import BankingAccessDenied, InvalidPayment
from repositories.access_repository import AccessRepository
from utils.banking_validation import parse_key


class AccessController(BaseController):
    def __init__(self):
        super().__init__(self.__class__.__name__)
        self.repository = AccessRepository(self.context)
        self.access = AccessPolicy(self.context, self.repository)

    def issue_credential(self, customer_key):
        self.access.require_internal()
        customer = self.repository.customer(parse_key(customer_key), lock=True)
        if customer is None:
            raise BankingEntityNotFound("customer")
        if customer.tipo != "ALUNO" or customer.situacao != "ATIVO" or self.repository.student(customer.chave) is None:
            raise BankingAccessDenied()
        token = token_urlsafe(32)
        self.repository.set_credential(customer.id, sha256(token.encode()).hexdigest(), datetime.now(timezone.utc))
        self.session.commit()
        return {"access_token": token, "token_type": "Bearer"}

    def configure(self, customer_key, payload):
        self.access.require_internal()
        organization = self.repository.customer(parse_key(customer_key), lock=True)
        if organization is None:
            raise BankingEntityNotFound("customer")
        if organization.tipo != "ORGANIZACAO_ESTUDANTIL" or organization.situacao != "ATIVO":
            raise InvalidPayment("An active organization is required.")
        members = []
        ids_by_key = {}
        for item in payload["members"]:
            student = self.repository.student(parse_key(item["customer_key"]))
            if student is None:
                raise InvalidPayment("Every member must be an active student.")
            ids_by_key[str(student.chave)] = student.id
            members.append((student.id, item["role"]))
        if len(ids_by_key) != len(members) or len(members) < 2:
            raise InvalidPayment("An organization requires at least two distinct members.")
        approver_keys = {str(parse_key(key)) for key in payload["approvers"]}
        if len(approver_keys) != 2 or not approver_keys <= ids_by_key.keys():
            raise InvalidPayment("Exactly two distinct members must be designated as approvers.")
        self.repository.replace_access(organization.id, members,
                                       [ids_by_key[key] for key in approver_keys], datetime.now(timezone.utc))
        result = {"customer_key": str(organization.chave), "members": len(members), "approvers": 2}
        self.session.commit()
        return result
