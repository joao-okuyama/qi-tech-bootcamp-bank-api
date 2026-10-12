from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError, IntegrityError

from tests.acceptance.conftest import api, banking, university, new_cpf
from tests.acceptance.test_bets import registry, destination
from tests.utils.db_utils import DbUtils


@pytest.fixture
def engine():
    engine = create_engine(DbUtils.database_url())
    yield engine
    engine.dispose()


@pytest.mark.parametrize("mode", ["missing", "expired", "empty"])
def test_unavailable_registry_blocks_only_company_destinations(banking, registry, engine, mode):
    sender, personal = banking.student(), banking.student()
    organization = destination(banking)
    banking.body(banking.deposit(sender["account"], 1000))
    with engine.begin() as connection:
        if mode == "missing":
            connection.execute(text("DELETE FROM empresas_bet_autorizadas"))
            connection.execute(text("UPDATE sincronizacao_empresas_bet SET atualizado_em = NULL, "
                                    "resumo_conteudo = NULL, quantidade = 0"))
        elif mode == "expired":
            connection.execute(text("UPDATE sincronizacao_empresas_bet SET atualizado_em = NOW() - INTERVAL '49 hours'"))
        else:
            connection.execute(text("DELETE FROM empresas_bet_autorizadas"))
    blocked = banking.transfer(sender, banking.payload(sender["account"], organization["account"]))
    assert blocked.status_code == 503 and blocked.json()["code"] == "QIT004001"
    assert banking.balance(sender["account"]) == 1000
    assert banking.transfer(sender, banking.payload(sender["account"], personal["account"])).status_code == 201


def test_failed_refresh_preserves_rows_and_last_success_timestamp(banking, registry, engine):
    with engine.connect() as connection:
        before = connection.execute(text("SELECT * FROM sincronizacao_empresas_bet")).one()
        rows = connection.execute(text("SELECT cnpj, razao_social FROM empresas_bet_autorizadas ORDER BY cnpj")).all()
    registry.response("invalid")
    assert registry.sync().status_code == 422
    with engine.connect() as connection:
        assert connection.execute(text("SELECT * FROM sincronizacao_empresas_bet")).one() == before
        assert connection.execute(text("SELECT cnpj, razao_social FROM empresas_bet_autorizadas ORDER BY cnpj")).all() == rows


def test_database_failure_during_refresh_rolls_back_deletion_and_metadata(banking, registry, engine):
    with engine.connect() as connection:
        before = connection.execute(text("SELECT * FROM sincronizacao_empresas_bet")).one()
        companies = connection.execute(text("SELECT cnpj, razao_social FROM empresas_bet_autorizadas ORDER BY cnpj")).all()
    with engine.begin() as connection:
        connection.execute(text("CREATE FUNCTION teste_falha_bet() RETURNS TRIGGER LANGUAGE plpgsql AS $$ "
                                "BEGIN RAISE EXCEPTION 'falha simulada'; END; $$"))
        connection.execute(text("CREATE TRIGGER teste_falha_bet BEFORE INSERT ON empresas_bet_autorizadas "
                                "FOR EACH ROW EXECUTE FUNCTION teste_falha_bet()"))
    try:
        assert registry.sync().status_code == 500
    finally:
        with engine.begin() as connection:
            connection.execute(text("DROP TRIGGER teste_falha_bet ON empresas_bet_autorizadas"))
            connection.execute(text("DROP FUNCTION teste_falha_bet()"))
    with engine.connect() as connection:
        assert connection.execute(text("SELECT * FROM sincronizacao_empresas_bet")).one() == before
        assert connection.execute(text("SELECT cnpj, razao_social FROM empresas_bet_autorizadas ORDER BY cnpj")).all() == companies


def test_transfer_waits_for_refresh_lock_and_uses_committed_snapshot(banking, registry, engine):
    sender, recipient = banking.student(), destination(banking)
    banking.body(banking.deposit(sender["account"], 1000))
    started = Event()
    with engine.connect() as connection, ThreadPoolExecutor(max_workers=1) as pool:
        transaction = connection.begin()
        connection.execute(text("SELECT id FROM sincronizacao_empresas_bet WHERE id=1 FOR UPDATE"))
        connection.execute(text("INSERT INTO empresas_bet_autorizadas (cnpj, razao_social) VALUES (:cnpj, 'Empresa simulada')"),
                           {"cnpj": recipient["cnpj"]})
        connection.execute(text("UPDATE sincronizacao_empresas_bet SET quantidade=quantidade+1"))
        def send():
            started.set()
            return banking.transfer(sender, banking.payload(sender["account"], recipient["account"]))
        request = pool.submit(send)
        assert started.wait(2)
        transaction.commit()
        assert request.result(timeout=20).status_code == 403
    assert banking.balance(sender["account"]) == 1000 and banking.balance(recipient["account"]) == 0


def test_numeric_states_initial_events_and_foreign_keys(banking, engine):
    student = banking.student()
    with engine.connect() as connection:
        row = connection.execute(text("SELECT c.id, c.status_id, s.codigo FROM cliente c "
                                      "JOIN status_cliente s ON s.id=c.status_id WHERE c.chave=:key"),
                                 {"key": student["customer"]}).one()
        assert row.status_id == 1 and row.codigo == "ATIVO"
        assert connection.execute(text("SELECT COUNT(*) FROM evento_status_cliente "
                                       "WHERE cliente_id=:id AND status_anterior_id IS NULL AND status_id=1"),
                                  {"id": row.id}).scalar_one() == 1
        assert connection.execute(text("SELECT COUNT(*) FROM evento_status_conta e "
                                       "JOIN conta c ON c.id=e.conta_id WHERE c.chave=:key AND e.status_id=1"),
                                  {"key": student["account"]}).scalar_one() == 1
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(text("UPDATE cliente SET status_id=99999 WHERE chave=:key"), {"key": student["customer"]})
    with pytest.raises(DBAPIError), engine.begin() as connection:
        connection.execute(text("DELETE FROM evento_status_cliente WHERE cliente_id=:id"), {"id": row.id})
