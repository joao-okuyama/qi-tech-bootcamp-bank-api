import json
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app import create_app
from constants import INTERNAL_TOKEN
from controllers.account_controller import AccountController
from controllers.customer_controller import CustomerController
from controllers.university_controller import UniversityController


@pytest.fixture
def client():
    with TestClient(create_app(), raise_server_exceptions=False) as client:
        yield client


@pytest.mark.parametrize("field,path", [
    ("name", "/university"), ("full_name", "/student"),
    ("email", "/student"), ("legal_name", "/student_organization"),
    ("trade_name", "/student_organization"), ("email", "/student_organization"),
])
@pytest.mark.parametrize("character", ["\x00", "\x1b", "\u202e", "\ud800"])
def test_registration_rejects_control_characters(client, session, field, path, character):
    payloads = {
        "/university": {"name": "Universidade"},
        "/student": {"university_key": str(uuid4()), "full_name": "Ana Silva",
                     "email": "ana@example.test", "cpf": "52998224725", "birthdate": "2000-01-01"},
        "/student_organization": {"university_key": str(uuid4()), "legal_name": "Organização",
                                  "trade_name": "Org", "email": "contato@example.test",
                                  "cnpj": "12ABC34501DE35"},
    }
    payload = payloads[path]
    payload[field] = character + payload[field]
    # JSON escape keeps invalid Unicode representable on the wire.
    response = client.post(path, content=json.dumps(payload),
                           headers={"INTERNAL-TOKEN": INTERNAL_TOKEN, "Content-Type": "application/json"})
    assert response.status_code == 422
    assert response.json()["code"] == "QIT002003"
    session.query.assert_not_called()


def test_duplicate_token_headers_are_rejected(client):
    response = client.get("/customer/invalid", headers=[
        ("INTERNAL-TOKEN", INTERNAL_TOKEN), ("INTERNAL-TOKEN", "wrong"),
    ])
    assert response.status_code == 403


def test_duplicate_bearer_headers_are_rejected_before_query(client, session):
    response = client.get(f"/account/{uuid4()}/balance", headers=[
        ("Authorization", "Bearer " + "a" * 43), ("Authorization", "Bearer " + "b" * 43),
    ])
    assert response.status_code == 403
    session.query.assert_not_called()


def test_statement_rejects_deep_offsets_before_query(client, session):
    response = client.get(f"/account/{uuid4()}/statement?limit=100&page=101",
                          headers={"INTERNAL-TOKEN": INTERNAL_TOKEN})
    assert response.status_code == 400
    assert response.json()["code"] == "QIT000010"
    session.query.assert_not_called()


def test_scalar_query_parameters_cannot_repeat(client, session):
    response = client.get(f"/account/{uuid4()}/statement?limit=1&limit=2",
                          headers={"INTERNAL-TOKEN": INTERNAL_TOKEN})
    assert response.status_code == 400
    session.query.assert_not_called()


@pytest.mark.parametrize("kind", ["student", "organization", "account", "university"])
def test_unknown_integrity_error_keeps_original_exception(kind, session):
    error = IntegrityError("statement", {}, Exception("no driver diagnostics"))
    if kind in ("student", "organization"):
        with pytest.raises(IntegrityError) as caught:
            controller = CustomerController()
            controller.repository = MagicMock()
            controller.university_repository = MagicMock()
            if kind == "student":
                controller.repository.create_student.side_effect = error
                controller.create_student({"cpf": "52998224725", "birthdate": "2000-01-01",
                                           "university_key": str(uuid4()), "full_name": "Ana",
                                           "email": "ana@example.test"})
            else:
                controller.repository.create_organization.side_effect = error
                controller.create_organization({"cnpj": "12ABC34501DE35", "university_key": str(uuid4()),
                                                "legal_name": "Org", "trade_name": "Org",
                                                "email": "contato@example.test"})
    elif kind == "account":
        controller = AccountController()
        controller.repository = MagicMock()
        controller.customer_repository = MagicMock()
        controller.customer_repository.get_by_key.return_value = SimpleNamespace(id=1, status=SimpleNamespace(codigo="ATIVO"))
        controller.repository.get_by_customer_id.return_value = None
        controller.repository.create.side_effect = error
        with pytest.raises(IntegrityError) as caught:
            controller.create(str(uuid4()))
    else:
        controller = UniversityController()
        controller.repository = MagicMock()
        controller.repository.create.side_effect = error
        with pytest.raises(IntegrityError) as caught:
            controller.create({"name": "Universidade"})
    assert caught.value is error
    session.rollback.assert_called_once()


def test_request_logger_does_not_record_query_values(client, monkeypatch):
    logger = MagicMock()
    monkeypatch.setattr("middlewares.request_logger.logger", logger)
    client.get("/unknown?email=private@example.test&token=secret", headers={"INTERNAL-TOKEN": INTERNAL_TOKEN})
    messages = str(logger.info.call_args_list)
    assert "private@example.test" not in messages
    assert "secret" not in messages


def test_statement_rejects_noninteger_page(client):
    response = client.get(f"/account/{uuid4()}/statement?page=1.5",
                          headers={"INTERNAL-TOKEN": INTERNAL_TOKEN})
    assert response.status_code == 400


def test_unexpected_error_rolls_back_closes_and_does_not_leak(client, session, monkeypatch):
    logger = MagicMock()
    monkeypatch.setattr("errors.handlers.logger", logger)
    monkeypatch.setattr("repositories.customer_repository.CustomerRepository.get_by_key",
                        MagicMock(side_effect=ValueError("private-cpf-and-password")))
    response = client.get(f"/customer/{uuid4()}", headers={"INTERNAL-TOKEN": INTERNAL_TOKEN})
    assert response.status_code == 500
    assert response.json()["code"] == "QIT000500"
    assert "private-cpf-and-password" not in response.text
    assert "private-cpf-and-password" not in str(logger.mock_calls)
    session.rollback.assert_called_once()
    session.close.assert_called_once()


@pytest.mark.parametrize("token", ["", "wrong", "café"])
def test_bad_token_is_forbidden_not_server_error(client, token):
    response = client.get("/customer/invalid", headers={"INTERNAL-TOKEN": token.encode("utf-8")})
    assert response.status_code == 403


def test_production_rejects_default_token(monkeypatch):
    import constants
    monkeypatch.setattr(constants, "APP_ENV", "production")
    monkeypatch.setattr(constants, "INTERNAL_TOKEN", "default_token")
    with pytest.raises(EnvironmentError, match="INTERNAL_TOKEN"):
        constants.check_variables()


@pytest.mark.parametrize("environment,name,allowed", [
    ("local", "bootcamp_test", "1"), ("test", "bootcamp", "1"),
    ("test", "bootcamp_test", "0"),
])
def test_database_reset_guard_rejects_unsafe_configuration(monkeypatch, environment, name, allowed):
    from tests.utils.db_utils import DbUtils
    monkeypatch.setenv("APP_ENV", environment)
    monkeypatch.setenv("DATABASE_URL", f"postgresql://test@localhost/{name}")
    monkeypatch.setenv("ALLOW_TEST_DATABASE_RESET", allowed)
    with pytest.raises(RuntimeError, match="banco dedicado"):
        DbUtils.database_url()
