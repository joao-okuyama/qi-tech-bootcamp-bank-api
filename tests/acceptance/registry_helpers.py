import os
import time
from hashlib import sha256
from uuid import uuid4

import requests


BASE_CNPJ = "12ABC34501DE35"


def csv_content(cnpjs):
    lines = ["Empresas autorizadas;;;;;;;;",
             ";PORTARIA;DENOMINACAO SOCIAL DA EMPRESA;CNPJ;MARCAS;DOMINIOS"]
    for index, cnpj in enumerate(cnpjs, 1):
        lines.append(f"{index};SPA;Empresa simulada {cnpj};{cnpj};Marca;example.test")
        lines.append(";(Alterada por portaria simulada);;;Outra marca;example.test")
    return "\ufeff" + "\n".join(lines) + "\n"


class Registry:
    def __init__(self, api):
        self.api = api
        self.url = os.environ["MOCKSERVER_URL"].rstrip("/")
        self.content = ""

    def response(self, content, status=200):
        self.content = content
        match = {"method": "GET", "path": "/bets.csv"}
        for attempt in range(60):
            try:
                response = requests.put(self.url + "/mockserver/clear", json=match, timeout=5)
                break
            except requests.ConnectionError:
                if attempt == 59:
                    raise
                time.sleep(0.5)
        response.raise_for_status()
        expectation = {"id": str(uuid4()), "httpRequest": match,
                       "httpResponse": {"statusCode": status,
                                        "headers": {"Content-Type": ["text/csv; charset=utf-8"]},
                                        "body": content}}
        response = requests.put(self.url + "/mockserver/expectation", json=expectation, timeout=10)
        response.raise_for_status()

    def companies(self, cnpjs):
        self.response(csv_content(cnpjs))

    def sync(self, reviewed=False):
        payload = {"reviewed_sha256": sha256(self.content.encode("utf-8")).hexdigest()} if reviewed else {}
        return self.api("POST", "/bet_registry/sync", json=payload)
