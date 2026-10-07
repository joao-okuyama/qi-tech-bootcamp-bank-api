import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError, DBAPIError

from tests.acceptance.conftest import api, banking, university, new_cpf
from tests.utils.db_utils import DbUtils


@pytest.fixture
def engine():
    engine = create_engine(DbUtils.database_url())
    yield engine
    engine.dispose()


def test_fee_credit_and_ledger_reconcile(banking, engine):
    a, b = banking.student(), banking.student()
    org = banking.organization([a, b])
    banking.body(banking.deposit(org["account"], 200000))
    key = banking.body(banking.transfer(a, banking.payload(org["account"], a["account"], 100000)))["transfer_key"]
    assert banking.decide(b, key).status_code == 200
    with engine.connect() as connection:
        rows = connection.execute(text("""
            SELECT m.tipo, m.valor_centavos FROM movimentacao_conta m
            JOIN transferencia t ON t.id = m.transferencia_id WHERE t.chave = :key
        """), {"key": key}).all()
        assert dict(rows) == {"DEBITO": 100000, "CREDITO": 100000, "TARIFA": 999, "RECEITA_TARIFA": 999}
        discrepancies = connection.execute(text("""
            SELECT c.id FROM conta c LEFT JOIN movimentacao_conta m ON m.conta_id = c.id
            GROUP BY c.id HAVING c.saldo_centavos <> COALESCE(SUM(
              CASE WHEN m.tipo IN ('DEBITO', 'TARIFA') THEN -m.valor_centavos ELSE m.valor_centavos END), 0)
        """)).all()
        assert discrepancies == []
        events = connection.execute(text("""
            SELECT s.codigo, e.aluno_responsavel_cliente_id FROM evento_status_transferencia e
            JOIN status_transferencia s ON s.id = e.status_id
            JOIN transferencia t ON t.id = e.transferencia_id
            WHERE t.chave = :key ORDER BY e.id
        """), {"key": key}).all()
        assert [e[0] for e in events] == ["CRIADA", "PENDENTE_APROVACAO", "APROVADA", "PROCESSANDO", "CONCLUIDA"]
        assert all(e[1] is not None for e in events)
        assert events[0][1] != events[2][1]


def test_failure_in_second_movement_rolls_back_entire_transfer(banking, engine):
    a, b = banking.student(), banking.student()
    banking.body(banking.deposit(a["account"], 100))
    payload = banking.payload(a["account"], b["account"])
    with engine.begin() as connection:
        connection.execute(text("""
            CREATE FUNCTION teste_falhar_credito() RETURNS TRIGGER LANGUAGE plpgsql AS $$
            BEGIN
                IF NEW.tipo = 'CREDITO' THEN RAISE EXCEPTION 'falha simulada'; END IF;
                RETURN NEW;
            END; $$;
            CREATE TRIGGER teste_falhar_credito BEFORE INSERT ON movimentacao_conta
            FOR EACH ROW EXECUTE FUNCTION teste_falhar_credito();
        """))
    try:
        assert banking.transfer(a, payload).status_code == 500
        assert (banking.balance(a["account"]), banking.balance(b["account"])) == (100, 0)
        with engine.connect() as connection:
            assert connection.execute(text("SELECT count(*) FROM transferencia WHERE chave_idempotencia = :key"),
                                      {"key": payload["idempotency_key"]}).scalar_one() == 0
    finally:
        with engine.begin() as connection:
            connection.execute(text("DROP TRIGGER teste_falhar_credito ON movimentacao_conta; DROP FUNCTION teste_falhar_credito();"))
    assert banking.transfer(a, payload).status_code == 201


@pytest.mark.parametrize("table", ["movimentacao_conta", "deposito", "evento_status_transferencia"])
@pytest.mark.parametrize("operation", ["UPDATE", "DELETE"])
def test_financial_history_rejects_edits(banking, engine, table, operation):
    a, b = banking.student(), banking.student()
    banking.body(banking.deposit(a["account"], 100))
    banking.body(banking.transfer(a, banking.payload(a["account"], b["account"])))
    query = f"UPDATE {table} SET id = id" if operation == "UPDATE" else f"DELETE FROM {table}"
    with pytest.raises(DBAPIError):
        with engine.begin() as connection:
            connection.execute(text(query))


def test_bank_account_is_not_a_customer_transfer_destination(banking, engine):
    a = banking.student()
    with engine.connect() as connection:
        key = str(connection.execute(text("SELECT chave FROM conta WHERE finalidade = 'RECEITA_TARIFAS'")).scalar_one())
    assert banking.transfer(a, banking.payload(a["account"], key)).status_code == 404
    assert banking.deposit(key, 100).status_code == 404
    assert banking.api("GET", f"/account/{key}/balance", headers=a["headers"]).status_code == 403


def test_blocked_account_cannot_send_or_receive(banking, engine):
    a, b = banking.student(), banking.student()
    banking.body(banking.deposit(a["account"], 100))
    with engine.begin() as connection:
        connection.execute(text("UPDATE conta SET status_id = (SELECT id FROM status_conta WHERE codigo = 'BLOQUEADA') WHERE chave = :key"), {"key": b["account"]})
    assert banking.transfer(a, banking.payload(a["account"], b["account"])).status_code == 422
    assert banking.deposit(b["account"], 100).status_code == 422
    assert banking.balance(a["account"]) == 100


def test_credential_is_stored_as_hash_only(banking, engine):
    a = banking.student()
    token = a["headers"]["Authorization"][7:]
    with engine.connect() as connection:
        stored = connection.execute(text("""
            SELECT cr.resumo_token FROM credencial_aluno cr JOIN cliente c ON c.id = cr.aluno_cliente_id
            WHERE c.chave = :key
        """), {"key": a["customer"]}).scalar_one()
    from hashlib import sha256
    assert stored == sha256(token.encode()).hexdigest() and stored != token


def test_customer_subtype_cannot_disagree_with_parent(banking, engine):
    a = banking.student()
    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            connection.execute(text("UPDATE cliente SET tipo = 'ORGANIZACAO_ESTUDANTIL' WHERE chave = :key"),
                               {"key": a["customer"]})
