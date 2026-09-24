from hashlib import sha256
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from controllers.access_controller import AccessController
from errors.banking_errors import BankingEntityNotFound
from errors.payment_errors import BankingAccessDenied


@pytest.fixture
def controller():
    controller = AccessController()
    controller.repository = MagicMock()
    controller.repository.customer.return_value = SimpleNamespace(
        id=1, chave=uuid4(), tipo="ALUNO", situacao="ATIVO",
    )
    return controller


@pytest.mark.parametrize("kind,status,has_registration", [
    ("ORGANIZACAO_ESTUDANTIL", "ATIVO", True),
    ("ALUNO", "BLOQUEADO", True),
    ("ALUNO", "ENCERRADO", True),
    ("ALUNO", "ATIVO", False),
])
def test_ineligible_customer_cannot_receive_credential(
    controller, session, kind, status, has_registration,
):
    customer = controller.repository.customer.return_value
    customer.tipo = kind
    customer.situacao = status
    if not has_registration:
        controller.repository.student.return_value = None

    with pytest.raises(BankingAccessDenied):
        controller.issue_credential(str(customer.chave))

    controller.repository.set_credential.assert_not_called()
    session.commit.assert_not_called()


def test_missing_customer_cannot_receive_credential(controller, session):
    controller.repository.customer.return_value = None
    with pytest.raises(BankingEntityNotFound):
        controller.issue_credential(str(uuid4()))
    controller.repository.set_credential.assert_not_called()
    session.commit.assert_not_called()


def test_credential_response_and_storage_use_different_values(controller, session):
    customer = controller.repository.customer.return_value
    result = controller.issue_credential(str(customer.chave))
    assert set(result) == {"access_token", "token_type"}
    assert result["token_type"] == "Bearer"
    assert len(result["access_token"]) >= 43

    controller.repository.customer.assert_called_once_with(customer.chave, lock=True)
    controller.repository.set_credential.assert_called_once()
    student_id, digest, created_at = controller.repository.set_credential.call_args.args
    assert student_id == customer.id
    assert digest == sha256(result["access_token"].encode()).hexdigest()
    assert created_at.tzinfo is not None
    session.commit.assert_called_once()
