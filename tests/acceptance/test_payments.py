from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest


def concurrently(first, second):
    barrier = Barrier(2)
    def call(function):
        barrier.wait(timeout=10)
        return function()
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(call, function) for function in (first, second)]
        return [f.result(timeout=30) for f in futures]


@pytest.mark.parametrize("rail", ["PIX", "TED"])
def test_personal_transfer_is_free_and_replay_does_not_move_money(banking, rail):
    a, b = banking.student(), banking.student()
    banking.body(banking.deposit(a["account"], 1000))
    payload = banking.payload(a["account"], b["account"], 100, rail)
    created = banking.body(banking.transfer(a, payload))
    assert created["status"] == "CONCLUIDA" and created["fee_cents"] == 0
    replay = banking.body(banking.transfer(a, payload), 200)
    assert replay == created
    assert (banking.balance(a["account"]), banking.balance(b["account"])) == (900, 100)
    assert len(banking.statement(a["account"])["data"]) == 2
    assert banking.transfer(a, dict(payload, amount_cents=101)).status_code == 409


def test_all_personal_teds_are_free(banking):
    a, b = banking.student(), banking.student()
    banking.body(banking.deposit(a["account"], 1000))
    for _ in range(5):
        result = banking.body(banking.transfer(a, banking.payload(a["account"], b["account"])))
        assert result["fee_cents"] == 0
    assert banking.balance(a["account"]) == 500


@pytest.mark.parametrize("amount,rail,fee", [(49, "TED", 0), (50, "TED", 1), (1050, "TED", 11),
                                         (99900, "TED", 999), (200000, "TED", 999), (200000, "PIX", 0)])
def test_organization_requires_independent_approval_and_correct_fee(banking, amount, rail, fee):
    a, b = banking.student(), banking.student()
    org = banking.organization([a, b])
    banking.body(banking.deposit(org["account"], amount + fee))
    payload = banking.payload(org["account"], a["account"], amount, rail)
    transfer = banking.body(banking.transfer(a, payload))
    key = transfer["transfer_key"]
    assert transfer["status"] == "PENDENTE_APROVACAO"
    assert transfer["fee_cents"] == fee
    assert banking.balance(org["account"]) == amount + fee
    assert banking.decide(a, key).status_code == 403
    completed = banking.body(banking.decide(b, key), 200)
    assert completed["status"] == "CONCLUIDA"
    assert completed["approver_customer_key"] == b["customer"]
    assert banking.body(banking.decide(b, key), 200) == completed
    assert banking.balance(org["account"]) == 0
    assert banking.balance(a["account"]) == amount
    assert len(banking.statement(org["account"])["data"]) == (3 if fee else 2)


def test_insufficient_balance_retains_approval_for_execution_retry(banking):
    a, b = banking.student(), banking.student()
    org = banking.organization([a, b])
    transfer = banking.body(banking.transfer(a, banking.payload(org["account"], a["account"])))
    key = transfer["transfer_key"]
    assert banking.body(banking.decide(b, key), 200)["status"] == "APROVADA"
    assert banking.statement(org["account"])["data"] == []
    banking.body(banking.deposit(org["account"], 101))
    result = banking.body(banking.decide(a, key, "execute"), 200)
    assert result["status"] == "CONCLUIDA" and result["approver_customer_key"] == b["customer"]
    assert banking.body(banking.decide(a, key, "execute"), 200) == result


def test_member_can_request_and_read_but_only_designated_student_can_approve(banking):
    a, b, c = banking.student(), banking.student(), banking.student()
    org = banking.organization([a, b, c])
    response = banking.api("GET", f"/account/{org['account']}/statement", headers=c["headers"])
    assert response.status_code == 200
    key = banking.body(banking.transfer(c, banking.payload(org["account"], c["account"])))["transfer_key"]
    assert banking.decide(c, key).status_code == 403
    assert banking.body(banking.decide(a, key), 200)["status"] == "APROVADA"


def test_rejection_cannot_be_approved_or_executed_later(banking):
    a, b = banking.student(), banking.student()
    org = banking.organization([a, b])
    key = banking.body(banking.transfer(a, banking.payload(org["account"], a["account"])))["transfer_key"]
    assert banking.body(banking.decide(b, key, "reject"), 200)["status"] == "RECUSADA"
    assert banking.decide(b, key).status_code == 409
    assert banking.decide(a, key, "execute").status_code in (403, 409)
    assert banking.statement(org["account"])["data"] == []


def test_revoked_approver_cannot_execute_previously_approved_transfer(banking):
    a, b, c = banking.student(), banking.student(), banking.student()
    org = banking.organization([a, b, c])
    key = banking.body(banking.transfer(a, banking.payload(org["account"], a["account"])))["transfer_key"]
    assert banking.body(banking.decide(b, key), 200)["status"] == "APROVADA"
    banking.configure(org["customer"], [a, b, c], [a, c])
    banking.body(banking.deposit(org["account"], 101))
    assert banking.decide(a, key, "execute").status_code == 403
    assert banking.balance(org["account"]) == 101


def test_individual_credentials_cannot_access_other_accounts_or_admin_routes(banking):
    a, b = banking.student(), banking.student()
    for suffix in ("", "/balance", "/statement"):
        assert banking.api("GET", f"/account/{b['account']}{suffix}", headers=a["headers"]).status_code == 403
    assert banking.api("GET", f"/customer/{b['customer']}", headers=a["headers"]).status_code == 403
    assert banking.transfer(b, banking.payload(a["account"], b["account"])).status_code == 403
    assert banking.api("POST", f"/account/{a['account']}/deposit", headers=a["headers"],
                       json={"amount_cents": 1, "reference": str(uuid4())}).status_code == 403
    assert banking.api("POST", f"/customer/{a['customer']}/credential",
                       headers=a["headers"], json={}).status_code == 403
    assert banking.api("GET", f"/account/{a['account']}/balance", headers={"Authorization": "Bearer " + "x" * 43}).status_code == 403
    assert banking.api("POST", "/transfer", json=banking.payload(a["account"], b["account"])).status_code == 403


def test_rotating_credential_invalidates_old_token(banking):
    a = banking.student()
    token = banking.body(banking.api("POST", f"/customer/{a['customer']}/credential", json={}))["access_token"]
    assert banking.api("GET", f"/account/{a['account']}/balance", headers=a["headers"]).status_code == 403
    assert banking.api("GET", f"/account/{a['account']}/balance",
                       headers={"Authorization": f"Bearer {token}"}).status_code == 200


@pytest.mark.parametrize("amount", [0, -1, True, 1.0, "100", 2**63])
def test_invalid_amount_never_changes_balances(banking, amount):
    a, b = banking.student(), banking.student()
    assert banking.transfer(a, banking.payload(a["account"], b["account"], amount)).status_code in (400, 422)
    assert banking.deposit(a["account"], amount).status_code in (400, 422)
    assert banking.balance(a["account"]) == banking.balance(b["account"]) == 0


def test_insufficient_personal_balance_and_same_account_are_rejected(banking):
    a, b = banking.student(), banking.student()
    assert banking.transfer(a, banking.payload(a["account"], b["account"])).status_code == 409
    assert banking.transfer(a, banking.payload(a["account"], a["account"])).status_code == 422
    assert banking.statement(a["account"])["data"] == []


def test_deposit_is_idempotent_and_reference_cannot_be_reused_elsewhere(banking):
    a, b = banking.student(), banking.student()
    reference = str(uuid4())
    first = banking.body(banking.deposit(a["account"], 100, reference))
    assert banking.body(banking.deposit(a["account"], 100, reference), 200) == first
    assert banking.deposit(a["account"], 101, reference).status_code == 409
    assert banking.deposit(b["account"], 100, reference).status_code == 409
    assert banking.balance(a["account"]) == 100 and banking.balance(b["account"]) == 0


def test_concurrent_same_key_creates_one_transfer(banking):
    a, b = banking.student(), banking.student()
    banking.body(banking.deposit(a["account"], 100))
    payload = banking.payload(a["account"], b["account"])
    results = concurrently(lambda: banking.transfer(a, payload), lambda: banking.transfer(a, payload))
    assert sorted(r.status_code for r in results) == [200, 201], [r.text for r in results]
    assert results[0].json() == results[1].json()
    assert (banking.balance(a["account"]), banking.balance(b["account"])) == (0, 100)


def test_concurrent_different_keys_cannot_overspend(banking):
    a, b = banking.student(), banking.student()
    banking.body(banking.deposit(a["account"], 100))
    results = concurrently(
        lambda: banking.transfer(a, banking.payload(a["account"], b["account"], 80)),
        lambda: banking.transfer(a, banking.payload(a["account"], b["account"], 80)))
    assert sorted(r.status_code for r in results) == [201, 409], [r.text for r in results]
    assert (banking.balance(a["account"]), banking.balance(b["account"])) == (20, 80)


def test_opposite_direction_transfers_do_not_deadlock(banking):
    a, b = banking.student(), banking.student()
    banking.body(banking.deposit(a["account"], 100))
    banking.body(banking.deposit(b["account"], 100))
    results = concurrently(
        lambda: banking.transfer(a, banking.payload(a["account"], b["account"], 30)),
        lambda: banking.transfer(b, banking.payload(b["account"], a["account"], 20)))
    assert [r.status_code for r in results] == [201, 201], [r.text for r in results]
    assert (banking.balance(a["account"]), banking.balance(b["account"])) == (90, 110)


def test_concurrent_approval_executes_once(banking):
    a, b = banking.student(), banking.student()
    org = banking.organization([a, b])
    banking.body(banking.deposit(org["account"], 101))
    key = banking.body(banking.transfer(a, banking.payload(org["account"], a["account"])))["transfer_key"]
    results = concurrently(lambda: banking.decide(b, key), lambda: banking.decide(b, key))
    assert [r.status_code for r in results] == [200, 200], [r.text for r in results]
    assert banking.balance(org["account"]) == 0 and banking.balance(a["account"]) == 100


def test_cursor_pagination_is_stable_when_new_movement_arrives(banking):
    a = banking.student()
    for _ in range(3):
        banking.body(banking.deposit(a["account"], 1))
    first = banking.statement(a["account"], limit=2)
    banking.body(banking.deposit(a["account"], 1))
    second = banking.statement(a["account"], limit=2, cursor=first["next_cursor"])
    keys = [m["movement_key"] for page in (first, second) for m in page["data"]]
    assert len(keys) == len(set(keys)) == 3
    assert second["is_last_page"]
    b = banking.student()
    assert banking.api("GET", f"/account/{b['account']}/statement",
                       params={"cursor": first["next_cursor"]}).status_code == 400


def test_credit_overflow_is_rejected_atomically(banking):
    a, b = banking.student(), banking.student()
    banking.body(banking.deposit(a["account"], 100))
    banking.body(banking.deposit(b["account"], 2**63 - 1))
    assert banking.deposit(b["account"], 1).status_code == 422
    assert banking.transfer(a, banking.payload(a["account"], b["account"])).status_code == 422
    assert banking.balance(a["account"]) == 100 and banking.balance(b["account"]) == 2**63 - 1


def test_concurrent_deposit_retry_credits_once(banking):
    a = banking.student()
    reference = str(uuid4())
    results = concurrently(lambda: banking.deposit(a["account"], 100, reference),
                           lambda: banking.deposit(a["account"], 100, reference))
    assert sorted(r.status_code for r in results) == [200, 201], [r.text for r in results]
    assert results[0].json() == results[1].json()
    assert banking.balance(a["account"]) == 100
    assert len(banking.statement(a["account"])["data"]) == 1


def test_concurrent_key_reuse_with_changed_payload_conflicts(banking):
    a, b = banking.student(), banking.student()
    banking.body(banking.deposit(a["account"], 1000))
    payload = banking.payload(a["account"], b["account"], 100)
    results = concurrently(lambda: banking.transfer(a, payload),
                           lambda: banking.transfer(a, dict(payload, amount_cents=200)))
    assert sorted(r.status_code for r in results) == [201, 409], [r.text for r in results]
    amount = next(r.json()["amount_cents"] for r in results if r.status_code == 201)
    assert (banking.balance(a["account"]), banking.balance(b["account"])) == (1000 - amount, amount)


@pytest.mark.parametrize("field,value", [
    ("fee_cents", 0), ("status", "CONCLUIDA"), ("requester_customer_key", str(uuid4())),
    ("approver_customer_key", str(uuid4())),
])
def test_transfer_rejects_client_supplied_authority_fields(banking, field, value):
    a, b = banking.student(), banking.student()
    payload = banking.payload(a["account"], b["account"])
    payload[field] = value
    assert banking.transfer(a, payload).status_code == 400
    assert banking.statement(a["account"])["data"] == []


def test_transfer_read_is_limited_to_participants(banking):
    a, b, outsider = banking.student(), banking.student(), banking.student()
    banking.body(banking.deposit(a["account"], 100))
    key = banking.body(banking.transfer(a, banking.payload(a["account"], b["account"])))["transfer_key"]
    for actor in (a, b):
        assert banking.api("GET", f"/transfer/{key}", headers=actor["headers"]).status_code == 200
    assert banking.api("GET", f"/transfer/{key}", headers=outsider["headers"]).status_code == 403


def test_approver_must_be_distinct_active_member_of_organization(banking):
    a, b, outsider = banking.student(), banking.student(), banking.student()
    org = banking.organization([a, b])
    members = [{"customer_key": member["customer"], "role": "MEMBRO"} for member in (a, b)]
    for approvers in ([a["customer"], a["customer"]], [a["customer"], outsider["customer"]]):
        response = banking.api("PUT", f"/customer/{org['customer']}/banking_access",
                               json={"members": members, "approvers": approvers})
        assert response.status_code in (400, 422)
    key = banking.body(banking.transfer(a, banking.payload(org["account"], a["account"])))["transfer_key"]
    assert banking.decide(outsider, key).status_code == 403
    assert banking.decide(a, key, "execute").status_code in (403, 409)
    assert banking.body(banking.decide(b, key), 200)["status"] == "APROVADA"
