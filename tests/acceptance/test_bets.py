from concurrent.futures import ThreadPoolExecutor

import pytest

from tests.acceptance.registry_helpers import BASE_CNPJ, Registry


@pytest.fixture
def registry(api):
    registry = Registry(api)
    registry.companies([BASE_CNPJ])
    response = registry.sync(reviewed=True)
    assert response.status_code == 200, response.text
    return registry


def destination(banking):
    a, b = banking.student(), banking.student()
    return banking.organization([a, b])


def assert_no_financial_effect(banking, accounts, before):
    assert [banking.balance(account) for account in accounts] == before
    assert all(banking.statement(account)["data"] == [] for account in accounts[1:])


@pytest.mark.parametrize("rail", ["PIX", "TED"])
def test_customer_cannot_transfer_to_listed_company(banking, registry, rail):
    sender, recipient = banking.student(), destination(banking)
    banking.body(banking.deposit(sender["account"], 1000))
    registry.companies([BASE_CNPJ, recipient["cnpj"]])
    assert registry.sync().status_code == 200
    accounts = [sender["account"], recipient["account"]]
    before = [banking.balance(account) for account in accounts]
    payload = banking.payload(*accounts, amount=100, rail=rail)
    first = banking.transfer(sender, payload)
    retry = banking.transfer(sender, payload)
    assert first.status_code == retry.status_code == 403
    assert first.json()["code"] == "QIT004004"
    assert_no_financial_effect(banking, accounts, before)
    assert [item["type"] for item in banking.statement(sender["account"])["data"]] == ["DEPOSITO"]


def test_unlisted_company_receives_transfer_and_replay_moves_nothing(banking, registry):
    sender, recipient = banking.student(), destination(banking)
    banking.body(banking.deposit(sender["account"], 1000))
    payload = banking.payload(sender["account"], recipient["account"])
    key = banking.body(banking.transfer(sender, payload))["transfer_key"]
    registry.companies([BASE_CNPJ, recipient["cnpj"]])
    assert registry.sync().status_code == 200
    replay = banking.body(banking.transfer(sender, payload), 200)
    assert replay["transfer_key"] == key and replay["status"] == "CONCLUIDA"
    assert banking.balance(sender["account"]) == 900
    assert banking.balance(recipient["account"]) == 100


def test_company_listed_while_waiting_for_approval_cannot_receive_funds(banking, registry):
    a, b = banking.student(), banking.student()
    source, recipient = banking.organization([a, b]), destination(banking)
    banking.body(banking.deposit(source["account"], 20000))
    transfer = banking.body(banking.transfer(a, banking.payload(source["account"], recipient["account"], 10000)))
    assert transfer["status"] == "PENDENTE_APROVACAO"
    registry.companies([BASE_CNPJ, recipient["cnpj"]])
    assert registry.sync().status_code == 200
    blocked = banking.decide(b, transfer["transfer_key"])
    assert blocked.status_code == 403 and blocked.json()["code"] == "QIT004004"
    current = banking.body(banking.api("GET", "/transfer/" + transfer["transfer_key"], headers=a["headers"]), 200)
    assert current["status"] == "PENDENTE_APROVACAO"
    assert banking.balance(source["account"]) == 20000
    assert banking.balance(recipient["account"]) == 0
    assert [row["type"] for row in banking.statement(source["account"])["data"]] == ["DEPOSITO"]


def test_previously_approved_transfer_rechecks_registry_before_execution(banking, registry):
    a, b = banking.student(), banking.student()
    source, recipient = banking.organization([a, b]), destination(banking)
    transfer = banking.body(banking.transfer(a, banking.payload(source["account"], recipient["account"])))
    key = transfer["transfer_key"]
    assert banking.body(banking.decide(b, key), 200)["status"] == "APROVADA"
    registry.companies([BASE_CNPJ, recipient["cnpj"]])
    assert registry.sync().status_code == 200
    banking.body(banking.deposit(source["account"], 1000))
    result = banking.api("POST", f"/transfer/{key}/execute", headers=a["headers"], json={})
    assert result.status_code == 403
    assert banking.balance(source["account"]) == 1000 and banking.balance(recipient["account"]) == 0
    assert banking.body(banking.api("GET", f"/transfer/{key}", headers=a["headers"]), 200)["status"] == "APROVADA"


@pytest.mark.parametrize("content,status", [
    ("", 200), ("<html>temporarily unavailable</html>", 200),
    (";PORTARIA;DENOMINACAO SOCIAL DA EMPRESA;CNPJ\n1;SPA;Empresa;00000000000000\n", 200),
    ("unavailable", 503),
])
def test_failed_refresh_preserves_existing_blocking(banking, registry, content, status):
    sender, recipient = banking.student(), destination(banking)
    banking.body(banking.deposit(sender["account"], 1000))
    registry.companies([BASE_CNPJ, recipient["cnpj"]])
    assert registry.sync().status_code == 200
    registry.response(content, status)
    result = registry.sync()
    assert result.status_code in (422, 503)
    blocked = banking.transfer(sender, banking.payload(sender["account"], recipient["account"]))
    assert blocked.status_code == 403 and blocked.json()["code"] == "QIT004004"
    assert banking.balance(sender["account"]) == 1000


def test_removal_requires_review_of_exact_downloaded_content(banking, registry):
    sender, recipient = banking.student(), destination(banking)
    banking.body(banking.deposit(sender["account"], 1000))
    registry.companies([BASE_CNPJ, recipient["cnpj"]])
    assert registry.sync().status_code == 200
    registry.companies([BASE_CNPJ])
    assert registry.sync().status_code == 409
    blocked = banking.transfer(sender, banking.payload(sender["account"], recipient["account"]))
    assert blocked.status_code == 403
    assert registry.sync(reviewed=True).status_code == 200
    assert banking.transfer(sender, banking.payload(sender["account"], recipient["account"])).status_code == 201


def test_student_cannot_refresh_registry_or_override_destination_identity(banking, registry):
    sender, recipient = banking.student(), destination(banking)
    result = banking.api("POST", "/bet_registry/sync", headers=sender["headers"], json={})
    assert result.status_code == 403
    banking.body(banking.deposit(sender["account"], 1000))
    payload = banking.payload(sender["account"], recipient["account"], destination_cnpj="not-listed")
    assert banking.transfer(sender, payload).status_code == 400
    assert banking.balance(sender["account"]) == 1000


def test_refresh_and_transfer_are_consistent_when_concurrent(banking, registry):
    sender, recipient = banking.student(), destination(banking)
    banking.body(banking.deposit(sender["account"], 1000))
    registry.companies([BASE_CNPJ, recipient["cnpj"]])
    with ThreadPoolExecutor(max_workers=2) as pool:
        refresh = pool.submit(registry.sync)
        transfer = pool.submit(banking.transfer, sender, banking.payload(sender["account"], recipient["account"]))
        assert refresh.result(timeout=30).status_code == 200
        result = transfer.result(timeout=30)
    assert result.status_code in (201, 403)
    received = 100 if result.status_code == 201 else 0
    assert banking.balance(recipient["account"]) == received
    assert banking.balance(sender["account"]) == 1000 - received
    assert banking.transfer(sender, banking.payload(sender["account"], recipient["account"])).status_code == 403
