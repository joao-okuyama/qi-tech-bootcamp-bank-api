import io
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from connectors.bet_registry_connector import BetRegistryConnector
from errors.bet_errors import BetRegistryUnavailable
from tests.acceptance.registry_helpers import BASE_CNPJ, csv_content
from utils.bet_registry import parse_bet_registry


def test_official_layout_preserves_cnpj_as_identifier_and_ignores_brand_continuations():
    rows = parse_bet_registry(csv_content([BASE_CNPJ]).encode("utf-8"))
    assert rows == [{"cnpj": BASE_CNPJ, "razao_social": "Empresa simulada " + BASE_CNPJ}]


def test_formatted_cnpj_is_normalized():
    csv = csv_content(["55.590.815/0001-60"])
    assert parse_bet_registry(csv)[0]["cnpj"] == "55590815000160"


@pytest.mark.parametrize("content", [
    "", "<html>erro</html>",
    ";PORTARIA;DENOMINACAO SOCIAL DA EMPRESA;CNPJ\n1;SPA;Empresa;00000000000000\n",
    ";PORTARIA;DENOMINACAO SOCIAL DA EMPRESA;CNPJ\n2;SPA;Empresa;12ABC34501DE35\n",
    ";PORTARIA;DENOMINACAO SOCIAL DA EMPRESA;CNPJ\n1;SPA;;12ABC34501DE35\n",
    ";PORTARIA;DENOMINACAO SOCIAL DA EMPRESA;CNPJ\n1;SPA;Empresa;12ABC34501DE35\n;SPA;Outra;\n",
])
def test_invalid_registry_is_rejected_as_a_whole(content):
    with pytest.raises(ValueError):
        parse_bet_registry(content)


class RawBody(io.BytesIO):
    def read1(self, size, decode_content=False):
        return super().read1(size)


def fake_response(content, status=200, mime="text/csv", **headers):
    response = MagicMock()
    response.status_code = status
    response.headers = {"Content-Type": mime, **headers}
    response.raw = RawBody(content)
    response.__enter__.return_value = response
    return response


def test_public_csv_request_does_not_leak_internal_credentials(monkeypatch):
    response = fake_response(b"csv")
    get = MagicMock(return_value=response)
    monkeypatch.setattr("connectors.bet_registry_connector.requests.get", get)
    assert BetRegistryConnector().download() == b"csv"
    options = get.call_args.kwargs
    assert "INTERNAL-TOKEN" not in options["headers"]
    assert options["allow_redirects"] is False and options["stream"] is True
    assert options["timeout"] > 0


@pytest.mark.parametrize("status,mime,headers", [
    (302, "text/csv", {}), (503, "text/csv", {}), (200, "text/html", {}),
    (200, "text/csv", {"Content-Encoding": "gzip"}),
    (200, "text/csv", {"Content-Length": "99999999"}),
    (200, "text/csv", {"Content-Length": "10"}),
])
def test_invalid_upstream_response_is_rejected(monkeypatch, status, mime, headers):
    monkeypatch.setattr("connectors.bet_registry_connector.requests.get",
                        MagicMock(return_value=fake_response(b"csv", status, mime, **headers)))
    with pytest.raises(BetRegistryUnavailable):
        BetRegistryConnector().download()


def test_unannounced_oversized_response_is_rejected(monkeypatch):
    monkeypatch.setattr("connectors.bet_registry_connector.requests.get",
                        MagicMock(return_value=fake_response(b"too large")))
    connector = BetRegistryConnector()
    connector.max_bytes = 2
    with pytest.raises(BetRegistryUnavailable):
        connector.download()


def test_refresh_is_authorized_before_download(session, monkeypatch):
    from controllers.bet_registry_controller import BetRegistryController
    from errors.payment_errors import BankingAccessDenied

    controller = BetRegistryController()
    controller.context.credential_type = "BEARER"
    download = MagicMock()
    monkeypatch.setattr(controller.connector, "download", download)
    with pytest.raises(BankingAccessDenied):
        controller.sync({})
    download.assert_not_called()
    session.query.assert_not_called()


def test_raw_upstream_data_is_never_returned_in_parser_errors(session, monkeypatch):
    from controllers.bet_registry_controller import BetRegistryController
    from errors.bet_errors import BetRegistryInvalid

    controller = BetRegistryController()
    monkeypatch.setattr(controller.connector, "download", lambda: b"private-upstream-content")
    with pytest.raises(BetRegistryInvalid) as error:
        controller.sync({})
    assert "private-upstream-content" not in error.value.description
    session.query.assert_not_called()


def test_rollback_is_left_to_middleware_after_repository_failure(session, monkeypatch):
    from controllers.bet_registry_controller import BetRegistryController

    controller = BetRegistryController()
    controller.connector = SimpleNamespace(download=lambda: csv_content([BASE_CNPJ]).encode("utf-8"))
    controller.repository = MagicMock()
    controller.repository.cnpjs.return_value = set()
    controller.repository.replace_all.side_effect = RuntimeError("database unavailable")
    with pytest.raises(RuntimeError):
        controller.sync({})
    session.commit.assert_not_called()


def test_snapshot_refreshed_after_request_started_is_not_mistaken_for_future_data():
    from controllers.payment_controller import PaymentController

    controller = PaymentController()
    controller.repository = MagicMock()
    controller.repository.customer.return_value = SimpleNamespace(id=1, tipo="ORGANIZACAO_ESTUDANTIL")
    controller.bet_repository = MagicMock()
    controller.bet_repository.snapshot.return_value = SimpleNamespace(
        atualizado_em=datetime.now(timezone.utc) - timedelta(seconds=1), quantidade=1)
    controller.bet_repository.count.return_value = 1
    controller.bet_repository.recipient_cnpj.return_value = BASE_CNPJ
    controller.bet_repository.by_cnpj.return_value = None
    request_started = datetime.now(timezone.utc) - timedelta(minutes=1)
    controller._require_allowed_destination(SimpleNamespace(cliente_id=1), request_started)
