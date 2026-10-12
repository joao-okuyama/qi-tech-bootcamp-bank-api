from database import Context
from models import Aluno, Cliente, EventoStatusCliente, OrganizacaoEstudantil


class CustomerRepository:
    def __init__(self, context: Context):
        self.session = context.db_session

    def create_student(self, data: dict, university_id: int, birthdate) -> Cliente:
        customer = Cliente(tipo="ALUNO")
        self.session.add(customer)
        self.session.flush()
        self.session.add(Aluno(
            cliente_id=customer.id,
            universidade_id=university_id,
            nome_completo=data["full_name"],
            email=data["email"],
            cpf=data["cpf"],
            data_nascimento=birthdate,
        ))
        self.session.flush()
        self.session.add(EventoStatusCliente(cliente_id=customer.id, status_id=customer.status_id,
                                            motivo="Cadastro do cliente"))
        self.session.refresh(customer, attribute_names=["status"])
        return customer

    def create_organization(self, data: dict, university_id: int) -> Cliente:
        customer = Cliente(tipo="ORGANIZACAO_ESTUDANTIL")
        self.session.add(customer)
        self.session.flush()
        self.session.add(OrganizacaoEstudantil(
            cliente_id=customer.id,
            universidade_id=university_id,
            razao_social=data["legal_name"],
            nome_fantasia=data["trade_name"],
            email=data["email"],
            cnpj=data["cnpj"],
        ))
        self.session.flush()
        self.session.add(EventoStatusCliente(cliente_id=customer.id, status_id=customer.status_id,
                                            motivo="Cadastro do cliente"))
        self.session.refresh(customer, attribute_names=["status"])
        return customer

    def get_by_key(self, key, for_update: bool = False) -> Cliente:
        query = self.session.query(Cliente).filter(Cliente.chave == key)
        if for_update:
            query = query.with_for_update()
        return query.first()

    def get_registration(self, customer: Cliente):
        model = Aluno if customer.tipo == "ALUNO" else OrganizacaoEstudantil
        return self.session.query(model).filter(model.cliente_id == customer.id).first()
