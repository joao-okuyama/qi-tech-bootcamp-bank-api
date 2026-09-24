from uuid import uuid4


class Banking:
    def __init__(self, api, university, new_cpf):
        self.api, self.university, self.new_cpf = api, university, new_cpf

    @staticmethod
    def body(response, status=201):
        assert response.status_code == status, response.text
        return response.json()

    def student(self):
        customer = self.body(self.api("POST", "/student", json={
            "university_key": self.university, "full_name": "Aluno Simulado",
            "email": f"{uuid4()}@example.test", "cpf": self.new_cpf(), "birthdate": "2000-01-01",
        }))["customer_key"]
        account = self.body(self.api("POST", f"/customer/{customer}/account", json={}))["account_key"]
        token = self.body(self.api("POST", f"/customer/{customer}/credential", json={}))["access_token"]
        return {"customer": customer, "account": account, "headers": {"Authorization": f"Bearer {token}"}}

    def organization(self, members):
        base = uuid4().hex[:12].upper()
        numbers = [ord(c) - 48 for c in base]
        for weights in ([5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2], [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]):
            remainder = sum(a * b for a, b in zip(numbers, weights)) % 11
            digit = 0 if remainder < 2 else 11 - remainder
            numbers.append(digit)
            base += str(digit)
        customer = self.body(self.api("POST", "/student_organization", json={
            "university_key": self.university, "legal_name": "Organizacao Simulada",
            "trade_name": "Org", "email": f"{uuid4()}@example.test", "cnpj": base,
        }))["customer_key"]
        account = self.body(self.api("POST", f"/customer/{customer}/account", json={}))["account_key"]
        self.configure(customer, members, members[:2])
        return {"customer": customer, "account": account}

    def configure(self, organization, members, approvers):
        return self.body(self.api("PUT", f"/customer/{organization}/banking_access", json={
            "members": [{"customer_key": m["customer"], "role": "MEMBRO"} for m in members],
            "approvers": [m["customer"] for m in approvers],
        }), 200)

    def deposit(self, account, amount, reference=None):
        return self.api("POST", f"/account/{account}/deposit",
                        json={"amount_cents": amount, "reference": reference or str(uuid4())})

    def balance(self, account):
        return self.body(self.api("GET", f"/account/{account}/balance"), 200)["balance_cents"]

    def payload(self, source, destination, amount=100, rail="TED", **extras):
        return dict(source_account_key=source, destination_account_key=destination,
                    amount_cents=amount, type=rail, idempotency_key=str(uuid4()), **extras)

    def transfer(self, actor, payload):
        return self.api("POST", "/transfer", headers=actor["headers"], json=payload)

    def decide(self, actor, key, action="approve"):
        return self.api("POST", f"/transfer/{key}/{action}", headers=actor["headers"], json={})

    def statement(self, account, **params):
        return self.body(self.api("GET", f"/account/{account}/statement", params=params), 200)
