from sqlalchemy import tuple_

from database import Context
from models import Conta, EventoStatusConta, MovimentacaoConta, Transferencia


class AccountRepository:
    def __init__(self, context: Context):
        self.session = context.db_session

    def create(self, customer_id: int) -> Conta:
        account = Conta(cliente_id=customer_id)
        self.session.add(account)
        self.session.flush()
        self.session.add(EventoStatusConta(conta_id=account.id, status_id=account.status_id,
                                          motivo="Abertura da conta"))
        self.session.refresh(account, attribute_names=["status"])
        return account

    def get_by_customer_id(self, customer_id: int) -> Conta:
        return self.session.query(Conta).filter(Conta.cliente_id == customer_id).first()

    def get_by_key(self, key) -> Conta:
        return self.session.query(Conta).filter(Conta.chave == key).first()

    def list_movements(self, account_id: int, limit: int, offset: int) -> list:
        return (
            self.session.query(MovimentacaoConta, Transferencia.chave, Transferencia.descricao)
            .outerjoin(Transferencia, Transferencia.id == MovimentacaoConta.transferencia_id)
            .filter(MovimentacaoConta.conta_id == account_id)
            .order_by(MovimentacaoConta.criado_em.desc(), MovimentacaoConta.id.desc())
            .limit(limit + 1).offset(offset).all()
        )

    def movement_cursor(self, account_id, key):
        return self.session.query(MovimentacaoConta).filter(
            MovimentacaoConta.conta_id == account_id, MovimentacaoConta.chave == key).first()

    def list_after_cursor(self, account_id, cursor, limit):
        return (self.session.query(MovimentacaoConta, Transferencia.chave, Transferencia.descricao)
                .outerjoin(Transferencia, Transferencia.id == MovimentacaoConta.transferencia_id)
                .filter(MovimentacaoConta.conta_id == account_id,
                        tuple_(MovimentacaoConta.criado_em, MovimentacaoConta.id) < (cursor.criado_em, cursor.id))
                .order_by(MovimentacaoConta.criado_em.desc(), MovimentacaoConta.id.desc())
                .limit(limit + 1).all())
