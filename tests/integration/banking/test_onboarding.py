from concurrent.futures import ThreadPoolExecutor
from os import environ
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text

from tests.utils import RandomGenerator
from tests.utils.db_utils import DbUtils
from tests.utils.requisition import ClientRequisition


def send(method, path, payload=None):
    response = ClientRequisition.send(
        method, path, payload=payload,
        headers={"INTERNAL-TOKEN": environ.get("INTERNAL_TOKEN", "default_token")},
    )
    return response.response_status, response.response_json


@pytest.fixture
def engine():
    engine = create_engine(DbUtils.database_url())
    yield engine
    engine.dispose()


@pytest.fixture
def university():
    status, result = send("POST", "/university", {"name": f"Universidade Teste {uuid4()}"})
    assert status == 201, result
    return result["university_key"]


def student_payload(university):
    return {
        "university_key": university, "full_name": "Aluno de Teste",
        "email": f"{uuid4()}@example.test",
        "cpf": RandomGenerator.generate_cpf().replace(".", "").replace("-", ""),
        "birthdate": "2000-01-01",
    }


def create_student(university):
    payload = student_payload(university)
    status, result = send("POST", "/student", payload)
    assert status == 201, result
    return result["customer_key"], payload


def test_student_without_org_can_open_account_and_consult(university, engine):
    key, payload = create_student(university)
    status, result = send("GET", f"/customer/{key}")
    assert status == 200 and result["type"] == "ALUNO"
    status, account = send("POST", f"/customer/{key}/account", {})
    assert status == 201, account
    account_key = account["account_key"]
    status, balance = send("GET", f"/account/{account_key}/balance")
    assert status == 200
    assert balance == {"account_key": account_key, "currency": "BRL", "balance_cents": 0}
    status, statement = send("GET", f"/account/{account_key}/statement")
    assert status == 200
    assert statement == {"data": [], "is_last_page": True, "limit": 20, "page": 0}
    with engine.connect() as connection:
        assert connection.execute(text(
            "SELECT count(*) FROM vinculo_organizacao v JOIN aluno a ON a.cliente_id = v.aluno_cliente_id "
            "WHERE a.cpf = :cpf"
        ), {"cpf": payload["cpf"]}).scalar_one() == 0


def make_cnpj():
    base = uuid4().hex[:12].upper()
    numbers = [ord(character) - 48 for character in base]
    for weights in ([5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2], [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]):
        remainder = sum(a * b for a, b in zip(numbers, weights)) % 11
        digit = 0 if remainder < 2 else 11 - remainder
        numbers.append(digit)
        base += str(digit)
    return base


def test_organization_registration_and_account(university, engine):
    payload = {
        "university_key": university, "legal_name": "Organização de Teste",
        "trade_name": "Org Teste", "email": f"{uuid4()}@example.test",
        "cnpj": make_cnpj(),
    }
    status, result = send("POST", "/student_organization", payload)
    assert status == 201, result
    assert result["type"] == "ORGANIZACAO_ESTUDANTIL"
    key = result["customer_key"]
    assert send("POST", f"/customer/{key}/account", {})[0] == 201
    assert send("POST", "/student_organization", payload)[0] == 409
    with engine.connect() as connection:
        assert connection.execute(text(
            "SELECT email FROM organizacao_estudantil WHERE cnpj = :cnpj"
        ), {"cnpj": payload["cnpj"]}).scalar_one() == payload["email"]


def test_duplicate_cpf_rolls_back_parent_row(university, engine):
    key, payload = create_student(university)
    payload["email"] = f"{uuid4()}@example.test"
    assert send("POST", "/student", payload)[0] == 409
    with engine.connect() as connection:
        assert connection.execute(text(
            "SELECT count(*) FROM cliente c LEFT JOIN aluno a ON a.cliente_id = c.id "
            "WHERE c.tipo = 'ALUNO' AND a.cliente_id IS NULL"
        )).scalar_one() == 0


def test_email_is_canonicalized_before_uniqueness(university):
    key, payload = create_student(university)
    payload["cpf"] = RandomGenerator.generate_cpf().replace(".", "").replace("-", "")
    payload["email"] = payload["email"].upper()
    assert send("POST", "/student", payload)[0] == 409


def test_concurrent_account_opening_creates_exactly_one(university, engine):
    key, payload = create_student(university)
    barrier = Barrier(2)

    def open_account():
        barrier.wait(timeout=10)
        return send("POST", f"/customer/{key}/account", {})[0]

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: open_account(), range(2)))
    assert sorted(results) == [201, 409]
    with engine.connect() as connection:
        assert connection.execute(text(
            "SELECT count(*) FROM conta co JOIN cliente c ON c.id = co.cliente_id WHERE c.chave = :key"
        ), {"key": key}).scalar_one() == 1


def test_blocked_customer_cannot_open_account(university, engine):
    key, payload = create_student(university)
    with engine.begin() as connection:
        connection.execute(text("UPDATE cliente SET situacao = 'BLOQUEADO' WHERE chave = :key"), {"key": key})
    assert send("POST", f"/customer/{key}/account", {})[0] == 409


@pytest.mark.parametrize("path", ["/customer/{key}", "/account/{key}", "/account/{key}/balance",
                                  "/account/{key}/statement"])
def test_unknown_key_returns_not_found(path):
    assert send("GET", path.format(key=uuid4()))[0] == 404


def test_invalid_birthdate_does_not_leave_customer(university, engine):
    payload = student_payload(university)
    payload["birthdate"] = "2026-02-30"
    assert send("POST", "/student", payload)[0] == 422
    with engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM aluno WHERE cpf = :cpf"),
                                  {"cpf": payload["cpf"]}).scalar_one() == 0


def test_statement_orders_ties_and_exposes_integer_amounts(university, engine):
    key, payload = create_student(university)
    status, account = send("POST", f"/customer/{key}/account", {})
    assert status == 201
    account_key = account["account_key"]
    with engine.begin() as connection:
        account_id = connection.execute(text("SELECT id FROM conta WHERE chave = :key"),
                                        {"key": account_key}).scalar_one()
        # Massa artificial do teste; não é uma rota pública de aporte.
        for amount in [100, 200, 300]:
            connection.execute(text(
                "INSERT INTO movimentacao_conta (conta_id, tipo, valor_centavos) "
                "VALUES (:account_id, 'APORTE_INICIAL', :amount)"
            ), {"account_id": account_id, "amount": amount})
        connection.execute(text("UPDATE conta SET saldo_centavos = 600 WHERE id = :id"), {"id": account_id})
    status, first = send("GET", f"/account/{account_key}/statement?limit=2")
    assert status == 200 and first["is_last_page"] is False
    assert [row["amount_cents"] for row in first["data"]] == [300, 200]
    status, second = send("GET", f"/account/{account_key}/statement?limit=2&page=1")
    assert status == 200 and second["is_last_page"] is True
    assert [row["amount_cents"] for row in second["data"]] == [100]
    assert all(row["transfer_key"] is None for row in first["data"])


def test_database_failure_rolls_back_and_next_registration_works(university, engine):
    payload = student_payload(university)
    with engine.begin() as connection:
        before = connection.execute(text("SELECT count(*) FROM cliente")).scalar_one()
        connection.execute(text("""
            CREATE FUNCTION rejeitar_cadastro_teste() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN RAISE EXCEPTION 'falha provocada para testar rollback'; END;
            $$
        """))
        connection.execute(text("""
            CREATE TRIGGER falha_cadastro_teste BEFORE INSERT ON aluno
            FOR EACH ROW EXECUTE FUNCTION rejeitar_cadastro_teste()
        """))
    try:
        status, result = send("POST", "/student", payload)
        assert status == 500 and result["code"] == "QIT000500"
        assert "falha provocada" not in str(result)
        with engine.connect() as connection:
            assert connection.execute(text("SELECT count(*) FROM cliente")).scalar_one() == before
    finally:
        with engine.begin() as connection:
            connection.execute(text("DROP TRIGGER falha_cadastro_teste ON aluno"))
            connection.execute(text("DROP FUNCTION rejeitar_cadastro_teste()"))
    assert send("POST", "/student", payload)[0] == 201


def test_statement_never_includes_another_account_movements(university, engine):
    first, _ = create_student(university)
    second, _ = create_student(university)
    _, account_a = send("POST", f"/customer/{first}/account", {})
    _, account_b = send("POST", f"/customer/{second}/account", {})
    with engine.begin() as connection:
        account_id = connection.execute(text("SELECT id FROM conta WHERE chave = :key"),
                                        {"key": account_b["account_key"]}).scalar_one()
        connection.execute(text("INSERT INTO movimentacao_conta (conta_id, tipo, valor_centavos) "
                                "VALUES (:id, 'APORTE_INICIAL', 123)"), {"id": account_id})
        connection.execute(text("UPDATE conta SET saldo_centavos = 123 WHERE id = :id"), {"id": account_id})
    status, statement = send("GET", f"/account/{account_a['account_key']}/statement")
    assert status == 200 and statement["data"] == []
    assert send("GET", f"/account/{account_b['account_key']}/statement")[1]["data"][0]["amount_cents"] == 123
