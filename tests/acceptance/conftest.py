import os
from uuid import uuid4

import pytest
import requests


_used_cpf_bases = set()


@pytest.fixture
def api():
    host = os.environ.get("SERVER_LOCALHOST", "127.0.0.1")
    port = os.environ.get("API_PORT", "3000")
    base_url = os.environ.get("API_BASE_URL", f"http://{host}:{port}")
    token = os.environ.get("INTERNAL_TOKEN", "default_token")

    def send(method, path, **kwargs):
        kwargs.setdefault("headers", {"INTERNAL-TOKEN": token})
        return requests.request(method, base_url + path, timeout=15, **kwargs)

    return send


@pytest.fixture
def university(api):
    response = api("POST", "/university", json={"name": f"Universidade {uuid4()}"})
    assert response.status_code == 201, response.text
    return response.json()["university_key"]


@pytest.fixture
def new_cpf():
    def generate():
        while True:
            base = f"{uuid4().int % 1_000_000_000:09}"
            if len(set(base)) > 1 and base not in _used_cpf_bases:
                _used_cpf_bases.add(base)
                break
        digits = [int(c) for c in base]
        for size in (10, 11):
            remainder = sum(n * w for n, w in zip(digits, range(size, 1, -1))) % 11
            digits.append(0 if remainder < 2 else 11 - remainder)
        return "".join(map(str, digits))
    return generate


@pytest.fixture
def student_payload(university, new_cpf):
    return {"university_key": university, "full_name": "Ana D'Ávila",
            "email": f"{uuid4()}@example.test", "cpf": new_cpf(),
            "birthdate": "2000-02-29"}


@pytest.fixture
def customer(api, student_payload):
    response = api("POST", "/student", json=student_payload)
    assert response.status_code == 201, response.text
    return response.json()["customer_key"]


@pytest.fixture
def account(api, customer):
    response = api("POST", f"/customer/{customer}/account", json={})
    assert response.status_code == 201, response.text
    return response.json()["account_key"]


@pytest.fixture
def banking(api, university, new_cpf):
    from tests.acceptance.payment_helpers import Banking
    return Banking(api, university, new_cpf)
