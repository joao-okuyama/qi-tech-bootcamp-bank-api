from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

from tests.acceptance.conftest import api
from tests.utils.db_utils import DbUtils, RESET_QUERIES


ROOT = Path(__file__).resolve().parents[3]


def test_upgrade_preserves_customers_email_balances_and_history(api):
    engine = create_engine(DbUtils.database_url(), isolation_level="AUTOCOMMIT")
    try:
        with engine.connect() as connection:
            for query in RESET_QUERIES:
                connection.exec_driver_sql(query)
            connection.exec_driver_sql((ROOT / "tests/fixtures/database_3abaacb.sql").read_text(encoding="utf-8"))
            connection.exec_driver_sql("""
                INSERT INTO universidade (nome) VALUES ('Universidade da migracao');
                INSERT INTO cliente (tipo) VALUES ('ALUNO'), ('ORGANIZACAO_ESTUDANTIL');
                INSERT INTO aluno (cliente_id, universidade_id, nome_completo, email, cpf, data_nascimento)
                VALUES (1, 1, 'Aluno Simulado', 'aluno@example.test', '52998224725', '2000-01-01');
                INSERT INTO organizacao_estudantil
                    (cliente_id, universidade_id, razao_social, nome_fantasia, email, cnpj)
                VALUES (2, 1, 'Organizacao Simulada', 'Org', 'contato@example.test', '12ABC34501DE35');
                INSERT INTO conta (cliente_id, saldo_centavos, situacao) VALUES (1, 12345, 'BLOQUEADA'), (2, 0, 'ATIVA');
                INSERT INTO deposito (conta_id, referencia, valor_centavos) VALUES (2, 'migracao-deposito', 12345);
                INSERT INTO movimentacao_conta (conta_id, deposito_id, tipo, valor_centavos) VALUES (2, 1, 'DEPOSITO', 12345);
                UPDATE cliente SET situacao='BLOQUEADO' WHERE id=1;
            """)
            before = connection.exec_driver_sql("SELECT chave, saldo_centavos FROM conta ORDER BY id").all()
            migration = (ROOT / "database/migrations/001_status_e_bets.sql").read_text(encoding="utf-8")
            connection.exec_driver_sql(migration)
            after = connection.exec_driver_sql("SELECT chave, saldo_centavos FROM conta ORDER BY id").all()
            assert before == after
            assert connection.exec_driver_sql("SELECT email FROM organizacao_estudantil").scalar_one() == "contato@example.test"
            assert connection.exec_driver_sql("SELECT codigo FROM status_cliente s JOIN cliente c ON s.id=c.status_id WHERE c.id=1").scalar_one() == "BLOQUEADO"
            assert connection.exec_driver_sql("SELECT codigo FROM status_conta s JOIN conta c ON s.id=c.status_id WHERE c.cliente_id=1").scalar_one() == "BLOQUEADA"
            assert connection.exec_driver_sql("SELECT COUNT(*) FROM movimentacao_conta").scalar_one() == 1
            assert connection.exec_driver_sql("SELECT COUNT(*) FROM deposito").scalar_one() == 1
            assert connection.exec_driver_sql("SELECT COUNT(*) FROM evento_status_cliente").scalar_one() == 2
            assert connection.exec_driver_sql("SELECT atualizado_em FROM sincronizacao_empresas_bet").scalar_one() is None
            organization = connection.exec_driver_sql("SELECT chave FROM cliente WHERE id=2").scalar_one()
            account = connection.exec_driver_sql("SELECT chave FROM conta WHERE cliente_id=2").scalar_one()
        result = api("GET", f"/customer/{organization}")
        assert result.status_code == 200 and result.json()["status"] == "ATIVO"
        result = api("GET", f"/account/{account}")
        assert result.status_code == 200 and result.json()["status"] == "ATIVA"
    finally:
        engine.dispose()
        DbUtils.rollback()
