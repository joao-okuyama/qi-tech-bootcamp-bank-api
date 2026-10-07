from datetime import datetime, timedelta, timezone

from controllers.access_policy import AccessPolicy
from controllers.base_controller import BaseController
from controllers.payment_policy import MAX_CENTS, calculate_fee, validate_amount
from constants import BET_REGISTRY_MAX_AGE_HOURS
from dtos.payment_dto import PaymentDTO
from errors.banking_errors import BankingEntityNotFound
from errors.payment_errors import BankingAccessDenied, InsufficientFunds, InvalidPayment, PaymentConflict
from errors.bet_errors import BetRegistryUnavailable, BettingTransferBlocked
from repositories.access_repository import AccessRepository
from repositories.payment_repository import PaymentRepository
from repositories.bet_repository import BetRepository
from utils.banking_validation import clean_registration_text, parse_key


class PaymentController(BaseController):
    def __init__(self):
        super().__init__(self.__class__.__name__)
        self.repository = PaymentRepository(self.context)
        self.access_repository = AccessRepository(self.context)
        self.access = AccessPolicy(self.context, self.access_repository)
        self.bet_repository = BetRepository(self.context)

    def create(self, payload):
        actor = self.access.actor()
        amount = validate_amount(payload["amount_cents"])
        key = clean_registration_text(payload["idempotency_key"], "idempotency_key")
        description = payload.get("description")
        if description is not None:
            description = clean_registration_text(description, "description")
        source, destination, customers = self._accounts(payload["source_account_key"], payload["destination_account_key"])
        now = datetime.now(timezone.utc)
        self._require_source(source, actor.id, now)
        existing = self.repository.existing_transfer(source.id, key)
        if existing is not None:
            expected = (destination.id, actor.id, amount, payload["type"], description)
            actual = (existing.conta_destino_id, existing.aluno_solicitante_cliente_id,
                      existing.valor_centavos, existing.tipo, existing.descricao)
            if actual != expected:
                raise PaymentConflict("The idempotency key was already used with a different request.")
            result = self._dto(existing)
            self.session.commit()
            return result, False
        customer = customers[source.cliente_id]
        self._require_allowed_destination(destination, now)
        is_organization = customer.tipo == "ORGANIZACAO_ESTUDANTIL"
        if is_organization:
            self._approvers(source.cliente_id, now)
        transfer = self.repository.create_transfer(
            conta_origem_id=source.id, conta_destino_id=destination.id,
            aluno_solicitante_cliente_id=actor.id, valor_centavos=amount,
            tarifa_centavos=calculate_fee(customer.tipo, payload["type"], amount),
            tipo=payload["type"], descricao=description, chave_idempotencia=key,
            status_id=self.repository.status("CRIADA").id, criado_em=now)
        self.repository.set_status(transfer, "CRIADA", actor.id, now)
        if is_organization:
            self.repository.set_status(transfer, "PENDENTE_APROVACAO", actor.id, now)
        else:
            self._execute(transfer, source, destination, actor.id, now, preserve_approval=False)
        result = self._dto(transfer)
        self.session.commit()
        return result, True

    def get(self, transfer_key):
        self.access.actor()
        transfer = self._transfer(transfer_key)
        source = self.repository.account(transfer.conta_origem_id)
        destination = self.repository.account(transfer.conta_destino_id)
        try:
            self.access.require_customer(source.cliente_id)
        except BankingAccessDenied:
            self.access.require_customer(destination.cliente_id)
        return self._dto(transfer)

    def decide(self, transfer_key, approve):
        actor = self.access.actor()
        transfer = self._transfer(transfer_key, lock=True)
        source, destination, customers = self._transfer_accounts(transfer)
        now = datetime.now(timezone.utc)
        self._require_source(source, transfer.aluno_solicitante_cliente_id, now)
        self._require_approver(transfer, source, actor.id, now)
        status = self.repository.status_code(transfer)
        if status == "PENDENTE_APROVACAO":
            if approve:
                self.repository.assign_approver(transfer, actor.id)
                self.repository.set_status(transfer, "APROVADA", actor.id, now)
                self._execute(transfer, source, destination, actor.id, now, preserve_approval=True)
            else:
                self.repository.set_status(transfer, "RECUSADA", actor.id, now)
        elif not ((approve and status in ("APROVADA", "CONCLUIDA")) or (not approve and status == "RECUSADA")):
            raise PaymentConflict("The transfer no longer accepts this decision.")
        result = self._dto(transfer)
        self.session.commit()
        return result

    def execute(self, transfer_key):
        actor = self.access.actor()
        transfer = self._transfer(transfer_key, lock=True)
        source, destination, customers = self._transfer_accounts(transfer)
        now = datetime.now(timezone.utc)
        if actor.id not in (transfer.aluno_solicitante_cliente_id, transfer.aluno_aprovador_cliente_id):
            raise BankingAccessDenied()
        self._require_source(source, transfer.aluno_solicitante_cliente_id, now)
        self._require_approver(transfer, source, transfer.aluno_aprovador_cliente_id, now)
        status = self.repository.status_code(transfer)
        if status == "APROVADA":
            self._execute(transfer, source, destination, actor.id, now, preserve_approval=True)
        elif status != "CONCLUIDA":
            raise PaymentConflict("Only an approved transfer can be executed.")
        result = self._dto(transfer)
        self.session.commit()
        return result

    def deposit(self, account_key, payload):
        self.access.require_internal()
        amount = validate_amount(payload["amount_cents"])
        reference = clean_registration_text(payload["reference"], "reference")
        key = parse_key(account_key)
        self.repository.lock_deposit_reference(reference)
        accounts = self.repository.lock_accounts([key])
        if not accounts:
            raise BankingEntityNotFound("account")
        account = accounts[0]
        existing = self.repository.existing_deposit(reference)
        if existing is not None:
            if (existing.conta_id, existing.valor_centavos) != (account.id, amount):
                raise PaymentConflict("The settlement reference was already used with a different deposit.")
            result = PaymentDTO.deposit(existing, account)
            self.session.commit()
            return result, False
        customer = self.repository.lock_customers([account.cliente_id])[0]
        if account.status.codigo != "ATIVA" or customer.status.codigo != "ATIVO":
            raise InvalidPayment("The destination account and customer must be active.")
        self._check_credit(account, amount)
        now = datetime.now(timezone.utc)
        deposit = self.repository.create_deposit(conta_id=account.id, referencia=reference,
                                                valor_centavos=amount, criado_em=now)
        self.repository.credit_balance(account, amount)
        self.repository.movement(account.id, "DEPOSITO", amount, now, deposit_id=deposit.id)
        result = PaymentDTO.deposit(deposit, account)
        self.session.commit()
        return result, True

    def _accounts(self, source_key, destination_key):
        keys = [parse_key(source_key), parse_key(destination_key)]
        if keys[0] == keys[1]:
            raise InvalidPayment("Source and destination must be different.")
        accounts = {row.chave: row for row in self.repository.lock_accounts(keys)}
        if len(accounts) != 2:
            raise BankingEntityNotFound("account")
        source, destination = (accounts[key] for key in keys)
        customers = {row.id: row for row in self.repository.lock_customers([source.cliente_id, destination.cliente_id])}
        if any(row.status.codigo != "ATIVA" for row in accounts.values()) or any(row.status.codigo != "ATIVO" for row in customers.values()):
            raise InvalidPayment("Both accounts and customers must be active.")
        return source, destination, customers

    def _transfer_accounts(self, transfer):
        source = self.repository.account(transfer.conta_origem_id)
        destination = self.repository.account(transfer.conta_destino_id)
        return self._accounts(str(source.chave), str(destination.chave))

    def _require_source(self, source, actor_id, now):
        actor = self.repository.customer(actor_id)
        if actor is None or actor.status.codigo != "ATIVO":
            raise BankingAccessDenied()
        if source.cliente_id == actor_id:
            return
        members = {row.aluno_cliente_id for row in self.access_repository.members(source.cliente_id, now)}
        if actor_id not in members:
            raise BankingAccessDenied()

    def _approvers(self, organization_id, now):
        members = {row.aluno_cliente_id for row in self.access_repository.members(organization_id, now)}
        approvers = {row.aluno_cliente_id for row in self.access_repository.approvers(organization_id, now)}
        if len(approvers) != 2 or not approvers <= members:
            raise PaymentConflict("The organization must have exactly two active member approvers.")
        return approvers

    def _require_approver(self, transfer, source, actor_id, now):
        if self.repository.customer(source.cliente_id).tipo != "ORGANIZACAO_ESTUDANTIL":
            raise PaymentConflict("Personal transfers do not use organizational approval.")
        if actor_id == transfer.aluno_solicitante_cliente_id or actor_id not in self._approvers(source.cliente_id, now):
            raise BankingAccessDenied()

    def _execute(self, transfer, source, destination, actor_id, now, preserve_approval):
        self._require_allowed_destination(destination, now)
        total = transfer.valor_centavos + transfer.tarifa_centavos
        if source.saldo_centavos < total:
            if preserve_approval:
                return
            raise InsufficientFunds()
        self._check_credit(destination, transfer.valor_centavos)
        revenue = None
        if transfer.tarifa_centavos:
            revenue = self.repository.revenue_account()
            if revenue.status.codigo != "ATIVA":
                raise PaymentConflict("The fee revenue account is unavailable.")
            self._check_credit(revenue, transfer.tarifa_centavos)
        self.repository.set_status(transfer, "PROCESSANDO", actor_id, now)
        self.repository.debit_balance(source, total)
        self.repository.credit_balance(destination, transfer.valor_centavos)
        self.repository.movement(source.id, "DEBITO", transfer.valor_centavos, now, transfer_id=transfer.id)
        self.repository.movement(destination.id, "CREDITO", transfer.valor_centavos, now, transfer_id=transfer.id)
        if revenue is not None:
            self.repository.credit_balance(revenue, transfer.tarifa_centavos)
            self.repository.movement(source.id, "TARIFA", transfer.tarifa_centavos, now, transfer_id=transfer.id)
            self.repository.movement(revenue.id, "RECEITA_TARIFA", transfer.tarifa_centavos, now, transfer_id=transfer.id)
        self.repository.complete(transfer, now)
        self.repository.set_status(transfer, "CONCLUIDA", actor_id, now)

    @staticmethod
    def _check_credit(account, amount):
        if account.saldo_centavos + amount > MAX_CENTS:
            raise InvalidPayment("The resulting balance exceeds the supported limit.")

    def _require_allowed_destination(self, destination, now):
        customer = self.repository.customer(destination.cliente_id)
        if customer.tipo != "ORGANIZACAO_ESTUDANTIL":
            return
        snapshot = self.bet_repository.snapshot()
        # Uma sincronizacao pode ter terminado enquanto aguardavamos este bloqueio.
        now = datetime.now(timezone.utc)
        if (snapshot is None or snapshot.atualizado_em is None or snapshot.atualizado_em > now
                or now - snapshot.atualizado_em >= timedelta(hours=BET_REGISTRY_MAX_AGE_HOURS)
                or snapshot.quantidade <= 0 or self.bet_repository.count() != snapshot.quantidade):
            raise BetRegistryUnavailable()
        cnpj = self.bet_repository.recipient_cnpj(customer.id)
        if cnpj is None:
            raise BetRegistryUnavailable()
        if self.bet_repository.by_cnpj(cnpj) is not None:
            raise BettingTransferBlocked()

    def _transfer(self, key, lock=False):
        transfer = self.repository.transfer(parse_key(key), lock=lock)
        if transfer is None:
            raise BankingEntityNotFound("transfer")
        return transfer

    def _dto(self, transfer):
        return PaymentDTO.transfer(transfer, self.repository.status_code(transfer),
            self.repository.account(transfer.conta_origem_id), self.repository.account(transfer.conta_destino_id),
            self.repository.customer(transfer.aluno_solicitante_cliente_id),
            self.repository.customer(transfer.aluno_aprovador_cliente_id) if transfer.aluno_aprovador_cliente_id else None)
