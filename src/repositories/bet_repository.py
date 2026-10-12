from models import EmpresaBetAutorizada, OrganizacaoEstudantil, SincronizacaoEmpresasBet


class BetRepository:
    def __init__(self, context):
        self.session = context.db_session

    def snapshot(self, exclusive=False):
        return (self.session.query(SincronizacaoEmpresasBet)
                .filter(SincronizacaoEmpresasBet.id == 1)
                .with_for_update(read=not exclusive).populate_existing().one_or_none())

    def by_cnpj(self, cnpj):
        return self.session.query(EmpresaBetAutorizada).filter(EmpresaBetAutorizada.cnpj == cnpj).first()

    def recipient_cnpj(self, customer_id):
        organization = self.session.get(OrganizacaoEstudantil, customer_id)
        return organization.cnpj if organization is not None else None

    def cnpjs(self):
        return {row[0] for row in self.session.query(EmpresaBetAutorizada.cnpj).all()}

    def count(self):
        return self.session.query(EmpresaBetAutorizada).count()

    def replace_all(self, companies, snapshot, digest, now):
        self.session.query(EmpresaBetAutorizada).delete(synchronize_session=False)
        self.session.add_all([EmpresaBetAutorizada(**company) for company in companies])
        snapshot.atualizado_em = now
        snapshot.resumo_conteudo = digest
        snapshot.quantidade = len(companies)
        self.session.flush()
