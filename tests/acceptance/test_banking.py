import json
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from threading import Barrier
from uuid import uuid4

import pytest


def assert_error(response, status, code):
    assert response.status_code == status, response.text
    body = response.json()
    assert set(body) == {"title", "description", "translation", "code"}
    assert body["code"] == code


@pytest.mark.parametrize("method,path", [
    ("POST", "/student"), ("POST", "/student_organization"), ("POST", "/university"),
    ("GET", "/customer/unknown"), ("GET", "/account/unknown/balance"),
    ("GET", "/account/unknown/statement"), ("OPTIONS", "/account/unknown"),
])
def test_private_routes_require_token(api, method, path):
    assert_error(api(method, path, headers={}), 403, "QIT000002")


def test_wrong_token_is_rejected(api):
    assert_error(api("GET", "/customer/unknown", headers={"INTERNAL-TOKEN": "wrong"}), 403, "QIT000002")


def test_health_check_is_public(api):
    assert api("GET", "/health_check", headers={}).status_code == 204


def test_student_without_organization_has_account_and_empty_statement(api, customer, account):
    response = api("GET", f"/customer/{customer}")
    assert response.status_code == 200
    assert set(response.json()) == {"customer_key", "type", "status", "created_at"}
    assert response.json()["type"] == "ALUNO"
    response = api("GET", f"/account/{account}")
    assert response.status_code == 200
    assert response.json()["status"] == "ATIVA"
    response = api("GET", f"/account/{account}/balance")
    assert response.status_code == 200
    assert response.json() == {"account_key": account, "balance_cents": 0, "currency": "BRL"}
    assert type(response.json()["balance_cents"]) is int
    response = api("GET", f"/account/{account}/statement")
    assert response.status_code == 200
    assert response.json() == {"data": [], "limit": 20, "page": 0, "is_last_page": True}


def test_duplicate_registration_and_following_request(api, student_payload):
    first = api("POST", "/student", json=student_payload)
    assert first.status_code == 201
    assert_error(api("POST", "/student", json=student_payload), 409, "QIT002002")
    assert api("GET", f"/customer/{first.json()['customer_key']}").status_code == 200


def test_email_uniqueness_is_case_insensitive(api, student_payload, new_cpf):
    first = dict(student_payload, cpf=new_cpf())
    response = api("POST", "/student", json=student_payload)
    assert response.status_code == 201
    first["email"] = student_payload["email"].upper()
    assert_error(api("POST", "/student", json=first), 409, "QIT002002")


def test_concurrent_first_account_returns_one_success(api, customer):
    barrier = Barrier(2)

    def create():
        barrier.wait(timeout=10)
        return api("POST", f"/customer/{customer}/account", json={})

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(create) for _ in range(2)]
        results = [future.result() for future in futures]
    assert sorted(r.status_code for r in results) == [201, 409]
    successful = next(r for r in results if r.status_code == 201)
    assert api("GET", f"/account/{successful.json()['account_key']}/balance").json()["balance_cents"] == 0
    assert_error(api("POST", f"/customer/{customer}/account", json={}), 409, "QIT002002")


@pytest.mark.parametrize("field,value,status", [
    ("cpf", "00000000000", 422), ("cpf", "52998224726", 422),
    ("cpf", "529.982.247-25", 400), ("birthdate", "2026-02-30", 422),
    ("birthdate", "2026-13-01", 422),
    ("full_name", "   ", 400), ("full_name", "Ana\x00Silva", 422),
    ("full_name", "Ana\u202eSilva", 422), ("full_name", "Ana\ud800", 422),
    ("email", "a\x00@example.test", 422),
    ("email", "İ" * 125 + "@e.test", 422),
])
def test_invalid_registration_can_be_corrected(api, student_payload, field, value, status):
    invalid = dict(student_payload, **{field: value})
    response = api("POST", "/student", data=json.dumps(invalid),
                   headers={"Content-Type": "application/json", **_token_header()})
    assert_error(response, status, "QIT000001" if status == 400 else "QIT002003")
    assert api("POST", "/student", json=student_payload).status_code == 201


def _token_header():
    import os
    return {"INTERNAL-TOKEN": os.environ.get("INTERNAL_TOKEN", "default_token")}


def test_future_birthdate_is_rejected(api, student_payload):
    student_payload["birthdate"] = (date.today() + timedelta(days=1)).isoformat()
    assert_error(api("POST", "/student", json=student_payload), 422, "QIT002003")


@pytest.mark.parametrize("path", ["/university/{key}", "/customer/{key}", "/account/{key}",
                                  "/account/{key}/balance", "/account/{key}/statement"])
def test_missing_entities_and_malformed_keys(api, path):
    assert_error(api("GET", path.format(key=uuid4())), 404, "QIT002001")
    assert_error(api("GET", path.format(key="invalid")), 400, "QIT000010")


@pytest.mark.parametrize("query,code", [
    ("limit=0", "QIT000001"), ("limit=101", "QIT000001"), ("page=-1", "QIT000001"),
    ("page=1.5", "QIT000001"), ("page=1000000", "QIT000001"),
    ("limit=100&page=101", "QIT000010"), ("limit=1&limit=2", "QIT000001"),
    ("page=0&page=1", "QIT000001"), ("unknown=1", "QIT000001"),
])
def test_statement_rejects_invalid_pagination(api, query, code):
    assert_error(api("GET", f"/account/{uuid4()}/statement?{query}"), 400, code)


def test_empty_statement_at_offset_limit(api, account):
    response = api("GET", f"/account/{account}/statement?limit=100&page=100")
    assert response.status_code == 200
    assert response.json() == {"data": [], "is_last_page": True, "page": 100, "limit": 100}


def test_cannot_set_balance_during_account_creation(api, customer):
    assert_error(api("POST", f"/customer/{customer}/account", json={"balance_cents": 100}), 400, "QIT000001")
    response = api("POST", f"/customer/{customer}/account", json={})
    assert response.status_code == 201
    assert api("GET", f"/account/{response.json()['account_key']}/balance").json()["balance_cents"] == 0


def test_university_normalization_and_conflict(api):
    name = f"Universidade São José {uuid4()}"
    response = api("POST", "/university", json={"name": f"  {name}  "})
    assert response.status_code == 201
    assert response.json()["name"] == name
    assert_error(api("POST", "/university", json={"name": name}), 409, "QIT002002")


def test_alphanumeric_cnpj_organization_can_open_account(api, university):
    cnpj = uuid4().hex[:12].upper()
    digits = [ord(c) - 48 for c in cnpj]
    for weights in ([5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2], [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]):
        remainder = sum(a * b for a, b in zip(digits, weights)) % 11
        digit = 0 if remainder < 2 else 11 - remainder
        digits.append(digit)
        cnpj += str(digit)
    payload = {"university_key": university, "legal_name": "Organização Estudantil",
               "trade_name": "Atlética", "email": f"{uuid4()}@example.test", "cnpj": cnpj}
    response = api("POST", "/student_organization", json=payload)
    assert response.status_code == 201, response.text
    assert response.json()["type"] == "ORGANIZACAO_ESTUDANTIL"
    assert "cnpj" not in response.json()
    assert api("POST", f"/customer/{response.json()['customer_key']}/account", json={}).status_code == 201
    assert_error(api("POST", "/student_organization", json=payload), 409, "QIT002002")
