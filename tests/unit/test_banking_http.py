from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app import create_app
from constants import INTERNAL_TOKEN
from errors.banking_errors import BankingEntityNotFound


@pytest.fixture
def client():
    with TestClient(create_app()) as client:
        yield client


@pytest.fixture
def headers():
    return {"INTERNAL-TOKEN": INTERNAL_TOKEN}


def test_internal_token_is_required(client, session):
    response = client.post("/student", json={})
    assert response.status_code == 403
    assert response.json()["code"] == "QIT000002"
    session.execute.assert_not_called()


@pytest.mark.parametrize("path,payload", [
    ("/student", {}),
    ("/university", {"name": "   "}),
    ("/university", {"name": "Universidade", "extra": True}),
    (f"/customer/{uuid4()}/account", {"balance_cents": 100}),
])
def test_schema_rejects_payload_before_business_logic(client, headers, path, payload, session):
    response = client.post(path, headers=headers, json=payload)
    assert response.status_code == 400
    assert response.json()["code"] == "QIT000001"
    session.query.assert_not_called()


@pytest.mark.parametrize("query", ["limit=0", "limit=101", "page=-1", "page=1000000", "unexpected=1"])
def test_statement_query_validation(client, headers, query, session):
    response = client.get(f"/account/{uuid4()}/statement?{query}", headers=headers)
    assert response.status_code == 400
    session.query.assert_not_called()


def test_invalid_uuid_is_400_not_500(client, headers, session):
    response = client.get("/account/not-a-uuid/balance", headers=headers)
    assert response.status_code == 400
    session.query.assert_not_called()


def test_post_returns_201_and_public_dto(client, headers, monkeypatch):
    controller = MagicMock()
    controller.create_student.return_value = {"customer_key": str(uuid4()), "type": "ALUNO"}
    monkeypatch.setattr("resources.customer.CustomerController", lambda: controller)
    payload = {"university_key": str(uuid4()), "full_name": "Aluno Teste",
               "email": "aluno@example.test", "cpf": "52998224725", "birthdate": "2000-01-01"}
    response = client.post("/student", headers=headers, json=payload)
    assert response.status_code == 201
    assert response.json() == controller.create_student.return_value
    controller.create_student.assert_called_once_with(payload)


def test_not_found_error_contract(client, headers, monkeypatch):
    controller = MagicMock()
    controller.get_by_key.side_effect = BankingEntityNotFound("customer")
    monkeypatch.setattr("resources.customer.CustomerController", lambda: controller)
    response = client.get(f"/customer/{uuid4()}", headers=headers)
    assert response.status_code == 404
    assert set(response.json()) == {"title", "code", "description", "translation"}


def test_statement_resource_maps_pagination(client, headers, monkeypatch):
    controller = MagicMock()
    controller.statement.return_value = {"data": [], "is_last_page": True, "limit": 2, "page": 3}
    monkeypatch.setattr("resources.account.AccountController", lambda: controller)
    key = str(uuid4())
    response = client.get(f"/account/{key}/statement?limit=2&page=3", headers=headers)
    assert response.status_code == 200
    assert response.json() == {"data": [], "limit": 2, "page": 3, "is_last_page": True}
    controller.statement.assert_called_once_with(key, 2, 3, None)
