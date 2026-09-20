from database import Context
from models import Conta, MovimentacaoConta, Transferencia


class AccountRepository:
    def __init__(self, context: Context):
        self.session = context.db_session

    def create(self, customer_id: int) -> Conta:
        account = Conta(cliente_id=customer_id)
        self.session.add(account)
        self.session.flush()
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
