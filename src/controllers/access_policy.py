from datetime import datetime, timezone

from errors.payment_errors import BankingAccessDenied
from repositories.access_repository import AccessRepository


class AccessPolicy:
    def __init__(self, context, repository=None):
        self.context = context
        self.repository = repository or AccessRepository(context)

    def require_internal(self):
        if self.context.credential_type != "INTERNAL":
            raise BankingAccessDenied()

    def actor(self):
        if self.context.credential_type != "BEARER" or self.context.credential_digest is None:
            raise BankingAccessDenied()
        actor = self.repository.actor(self.context.credential_digest)
        if actor is None:
            raise BankingAccessDenied()
        return actor

    def require_customer(self, customer_id):
        if self.context.credential_type == "INTERNAL":
            return
        actor = self.actor()
        if actor.id == customer_id:
            return
        now = datetime.now(timezone.utc)
        members = {row.aluno_cliente_id for row in self.repository.members(customer_id, now)}
        if actor.id not in members:
            raise BankingAccessDenied()
