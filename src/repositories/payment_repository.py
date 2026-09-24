from hashlib import sha256

from sqlalchemy import text

from models import (Cliente, Conta, Deposito, EventoStatusTransferencia,
                    MovimentacaoConta, StatusTransferencia, Transferencia)


class PaymentRepository:
    def __init__(self, context):
        self.session = context.db_session

    def lock_accounts(self, keys):
        return (self.session.query(Conta).filter(Conta.chave.in_(keys), Conta.finalidade == "CLIENTE")
                .order_by(Conta.id).with_for_update().populate_existing().all())

    def lock_customers(self, ids):
        return (self.session.query(Cliente).filter(Cliente.id.in_(ids)).order_by(Cliente.id)
                .with_for_update(read=True).populate_existing().all())

    def revenue_account(self):
        return (self.session.query(Conta).filter(Conta.finalidade == "RECEITA_TARIFAS")
                .with_for_update().populate_existing().one())

    def account(self, account_id):
        return self.session.get(Conta, account_id)

    def customer(self, customer_id):
        return self.session.get(Cliente, customer_id)

    def existing_transfer(self, source_id, key):
        return (self.session.query(Transferencia).filter(Transferencia.conta_origem_id == source_id,
                Transferencia.chave_idempotencia == key).first())

    def transfer(self, key, lock=False):
        query = self.session.query(Transferencia).filter(Transferencia.chave == key)
        return (query.with_for_update() if lock else query).first()

    def status(self, code):
        return self.session.query(StatusTransferencia).filter(StatusTransferencia.codigo == code).one()

    def status_code(self, transfer):
        return self.session.get(StatusTransferencia, transfer.status_id).codigo

    def set_status(self, transfer, code, actor_id, now):
        transfer.status_id = self.status(code).id
        self.session.add(EventoStatusTransferencia(transferencia_id=transfer.id,
                         status_id=transfer.status_id, aluno_responsavel_cliente_id=actor_id, ocorrido_em=now))

    def create_transfer(self, **values):
        transfer = Transferencia(**values)
        self.session.add(transfer)
        self.session.flush()
        return transfer

    @staticmethod
    def assign_approver(transfer, approver_id):
        transfer.aluno_aprovador_cliente_id = approver_id

    @staticmethod
    def debit_balance(account, amount):
        account.saldo_centavos -= amount

    @staticmethod
    def credit_balance(account, amount):
        account.saldo_centavos += amount

    @staticmethod
    def complete(transfer, now):
        transfer.concluido_em = now

    def movement(self, account_id, kind, amount, now, transfer_id=None, deposit_id=None):
        self.session.add(MovimentacaoConta(conta_id=account_id, tipo=kind, valor_centavos=amount,
                         transferencia_id=transfer_id, deposito_id=deposit_id, criado_em=now))

    def lock_deposit_reference(self, reference):
        lock_id = int.from_bytes(sha256(reference.encode()).digest()[:8], "big", signed=True)
        self.session.execute(text("SELECT pg_advisory_xact_lock(:lock_id)"), {"lock_id": lock_id})

    def existing_deposit(self, reference):
        return self.session.query(Deposito).filter(Deposito.referencia == reference).first()

    def create_deposit(self, **values):
        deposit = Deposito(**values)
        self.session.add(deposit)
        self.session.flush()
        return deposit
