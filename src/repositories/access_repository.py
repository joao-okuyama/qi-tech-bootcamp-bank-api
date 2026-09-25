from sqlalchemy import and_, or_

from models import Aluno, Cliente, CredencialAluno, DesignacaoAprovador, VinculoOrganizacao


class AccessRepository:
    def __init__(self, context):
        self.session = context.db_session

    def actor(self, digest):
        return (self.session.query(Cliente).join(Aluno, Aluno.cliente_id == Cliente.id)
                .join(CredencialAluno, CredencialAluno.aluno_cliente_id == Cliente.id)
                .filter(CredencialAluno.resumo_token == digest, Cliente.situacao == "ATIVO").first())

    def customer(self, key, lock=False):
        query = self.session.query(Cliente).filter(Cliente.chave == key)
        return (query.with_for_update() if lock else query).first()

    def student(self, key):
        return (self.session.query(Cliente).join(Aluno, Aluno.cliente_id == Cliente.id)
                .filter(Cliente.chave == key, Cliente.situacao == "ATIVO").first())

    def set_credential(self, student_id, digest, now):
        row = self.session.get(CredencialAluno, student_id)
        if row is None:
            row = CredencialAluno(aluno_cliente_id=student_id)
            self.session.add(row)
        row.resumo_token = digest
        row.criado_em = now

    @staticmethod
    def active(model, now):
        return and_(model.inicio_vigencia <= now,
                    or_(model.fim_vigencia.is_(None), model.fim_vigencia > now))

    def members(self, organization_id, now):
        return (self.session.query(VinculoOrganizacao)
                .filter(VinculoOrganizacao.organizacao_cliente_id == organization_id,
                        self.active(VinculoOrganizacao, now)).all())

    def approvers(self, organization_id, now):
        return (self.session.query(DesignacaoAprovador)
                .join(Cliente, Cliente.id == DesignacaoAprovador.aluno_cliente_id)
                .filter(DesignacaoAprovador.organizacao_cliente_id == organization_id,
                        Cliente.situacao == "ATIVO", self.active(DesignacaoAprovador, now)).all())

    def replace_access(self, organization_id, members, approvers, now):
        for model in (VinculoOrganizacao, DesignacaoAprovador):
            rows = self.session.query(model).filter(
                model.organizacao_cliente_id == organization_id, model.fim_vigencia.is_(None)).all()
            for row in rows:
                row.fim_vigencia = now
        self.session.flush()
        for student_id, role in members:
            self.session.add(VinculoOrganizacao(organizacao_cliente_id=organization_id,
                             aluno_cliente_id=student_id, papel=role, inicio_vigencia=now))
        for student_id in approvers:
            self.session.add(DesignacaoAprovador(organizacao_cliente_id=organization_id,
                             aluno_cliente_id=student_id, inicio_vigencia=now))
