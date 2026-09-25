from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from controllers.account_controller import AccountController
from controllers.customer_controller import CustomerController
from controllers.university_controller import UniversityController
from dtos.account_dto import AccountDTO
from errors.banking_errors import (
    BankingEntityNotFound, BankingRegistrationConflict, CustomerCannotOpenAccount,
)


def entity(**fields):
    return SimpleNamespace(
        id=1, chave=uuid4(), criado_em=datetime.now(timezone.utc), **fields,
    )


def integrity_error(constraint):
    original = Exception("database constraint")
    original.diag = SimpleNamespace(constraint_name=constraint)
    return IntegrityError("statement", {}, original)


@pytest.fixture
def customer_controller():
    controller = CustomerController()
    controller.repository = MagicMock()
    controller.university_repository = MagicMock()
    controller.university_repository.get_by_key.return_value = entity(nome="Universidade")
    controller.repository.create_student.return_value = entity(tipo="ALUNO", situacao="ATIVO")
    controller.repository.create_organization.return_value = entity(tipo="ORGANIZACAO_ESTUDANTIL", situacao="ATIVO")
    return controller


@pytest.fixture
def student_payload():
    return {"university_key": str(uuid4()), "full_name": "Aluno Teste",
            "email": "aluno@example.test", "cpf": "52998224725", "birthdate": "2000-01-01"}


def test_creates_student_without_membership(customer_controller, student_payload, session):
    result = customer_controller.create_student(student_payload)
    assert result["type"] == "ALUNO"
    assert "id" not in result and "cpf" not in result
    session.commit.assert_called_once()
    customer_controller.repository.create_student.assert_called_once()


def test_creates_organization(customer_controller, session):
    result = customer_controller.create_organization({
        "university_key": str(uuid4()), "cnpj": "12ABC34501DE35",
        "legal_name": "Organização Teste", "trade_name": "Org",
        "email": "CONTATO@EXAMPLE.TEST",
    })
    assert result["type"] == "ORGANIZACAO_ESTUDANTIL"
    session.commit.assert_called_once()
    payload = customer_controller.repository.create_organization.call_args.args[0]
    assert payload["email"] == "contato@example.test"


def test_missing_university_does_not_create_customer(customer_controller, student_payload, session):
    customer_controller.university_repository.get_by_key.return_value = None
    with pytest.raises(BankingEntityNotFound):
        customer_controller.create_student(student_payload)
    customer_controller.repository.create_student.assert_not_called()
    session.commit.assert_not_called()


@pytest.mark.parametrize("constraint", ["unico_aluno_cpf", "unico_aluno_email"])
def test_duplicate_student_rolls_back_whole_registration(customer_controller, student_payload, session, constraint):
    customer_controller.repository.create_student.side_effect = integrity_error(constraint)
    with pytest.raises(BankingRegistrationConflict):
        customer_controller.create_student(student_payload)
    session.rollback.assert_called_once()
    session.commit.assert_not_called()


def test_commit_failure_is_not_reported_as_success(customer_controller, student_payload, session):
    session.commit.side_effect = integrity_error("unico_aluno_email")
    with pytest.raises(BankingRegistrationConflict):
        customer_controller.create_student(student_payload)
    session.rollback.assert_called_once()


def test_unknown_database_failure_is_not_disguised_as_duplicate(customer_controller, student_payload, session):
    customer_controller.repository.create_student.side_effect = integrity_error("unexpected_constraint")
    with pytest.raises(IntegrityError):
        customer_controller.create_student(student_payload)
    session.rollback.assert_called_once()


@pytest.fixture
def account_controller():
    controller = AccountController()
    controller.repository = MagicMock()
    controller.customer_repository = MagicMock()
    controller.customer_repository.get_by_key.return_value = entity(tipo="ALUNO", situacao="ATIVO")
    controller.repository.get_by_customer_id.return_value = None
    controller.repository.create.return_value = entity(
        moeda="BRL", situacao="ATIVA", saldo_centavos=0,
    )
    return controller


def test_opening_account_locks_customer_before_creating(account_controller, session):
    customer = account_controller.customer_repository.get_by_key.return_value
    result = account_controller.create(str(customer.chave))
    account_controller.customer_repository.get_by_key.assert_called_once_with(customer.chave, for_update=True)
    account_controller.repository.create.assert_called_once_with(customer.id)
    assert result["status"] == "ATIVA"
    session.commit.assert_called_once()


@pytest.mark.parametrize("status", ["BLOQUEADO", "ENCERRADO"])
def test_inactive_customer_cannot_open_account(account_controller, status, session):
    account_controller.customer_repository.get_by_key.return_value.situacao = status
    with pytest.raises(CustomerCannotOpenAccount):
        account_controller.create(str(uuid4()))
    account_controller.repository.create.assert_not_called()
    session.commit.assert_not_called()


def test_incomplete_customer_cannot_open_account(account_controller):
    account_controller.customer_repository.get_registration.return_value = None
    with pytest.raises(CustomerCannotOpenAccount):
        account_controller.create(str(uuid4()))
    account_controller.repository.create.assert_not_called()


def test_missing_customer_cannot_open_account(account_controller):
    account_controller.customer_repository.get_by_key.return_value = None
    with pytest.raises(BankingEntityNotFound):
        account_controller.create(str(uuid4()))


def test_repeated_account_creation_is_conflict(account_controller, session):
    account_controller.repository.get_by_customer_id.return_value = entity()
    with pytest.raises(BankingRegistrationConflict):
        account_controller.create(str(uuid4()))
    account_controller.repository.create.assert_not_called()
    session.commit.assert_not_called()


def test_account_unique_conflict_is_also_handled(account_controller, session):
    account_controller.repository.create.side_effect = integrity_error("unico_conta_cliente")
    with pytest.raises(BankingRegistrationConflict):
        account_controller.create(str(uuid4()))
    session.rollback.assert_called_once()


def test_balance_is_integer_cents(account_controller, session):
    account_controller.repository.get_by_key.return_value = entity(
        cliente_id=1, saldo_centavos=101, moeda="BRL"
    )
    assert account_controller.get_balance(str(uuid4()))["balance_cents"] == 101
    session.commit.assert_not_called()


@pytest.mark.parametrize("kind,direction", [("DEBITO", "DEBIT"), ("TARIFA", "DEBIT"),
                                           ("CREDITO", "CREDIT"), ("APORTE_INICIAL", "CREDIT")])
def test_statement_keeps_amount_positive_and_explains_direction(kind, direction):
    movement = entity(tipo=kind, valor_centavos=1)
    result = AccountDTO.movement_to_dict(movement, None, None)
    assert result["amount_cents"] == 1 and result["direction"] == direction
    assert result["transfer_key"] is None


def test_statement_uses_extra_row_for_pagination(account_controller, session):
    account_controller.repository.get_by_key.return_value = entity(cliente_id=1)
    rows = [(entity(tipo="CREDITO", valor_centavos=100), uuid4(), "Teste") for _ in range(3)]
    account_controller.repository.list_movements.return_value = rows
    result = account_controller.get_statement(str(uuid4()), 2, 4)
    assert len(result["data"]) == 2 and result["is_last_page"] is False
    account_controller.repository.list_movements.assert_called_once_with(1, 2, 4)
    session.commit.assert_not_called()


def test_empty_statement(account_controller):
    account_controller.repository.get_by_key.return_value = entity(cliente_id=1)
    account_controller.repository.list_movements.return_value = []
    assert account_controller.get_statement(str(uuid4()), 20, 0) == {"data": [], "is_last_page": True}


def test_duplicate_university(session):
    controller = UniversityController()
    controller.repository = MagicMock()
    controller.repository.create.side_effect = integrity_error("unico_universidade_nome")
    with pytest.raises(BankingRegistrationConflict):
        controller.create({"name": "Universidade"})
    session.rollback.assert_called_once()
