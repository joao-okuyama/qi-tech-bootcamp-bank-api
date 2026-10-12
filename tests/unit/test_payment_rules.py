import pytest

from errors.payment_errors import InvalidPayment
from controllers.payment_policy import MAX_CENTS, calculate_fee, validate_amount


@pytest.mark.parametrize("customer,rail,amount,expected", [
    ("ALUNO", "TED", MAX_CENTS, 0), ("ALUNO", "PIX", 1, 0),
    ("ORGANIZACAO_ESTUDANTIL", "PIX", MAX_CENTS, 0),
    ("ORGANIZACAO_ESTUDANTIL", "TED", 49, 0),
    ("ORGANIZACAO_ESTUDANTIL", "TED", 50, 1),
    ("ORGANIZACAO_ESTUDANTIL", "TED", 149, 1),
    ("ORGANIZACAO_ESTUDANTIL", "TED", 150, 2),
    ("ORGANIZACAO_ESTUDANTIL", "TED", 99900, 999),
    ("ORGANIZACAO_ESTUDANTIL", "TED", MAX_CENTS, 999),
])
def test_fee_is_integer_and_rounded_half_up(customer, rail, amount, expected):
    result = calculate_fee(customer, rail, amount)
    assert result == expected and type(result) is int


@pytest.mark.parametrize("amount", [0, -1, True, False, 1.0, "1", None, MAX_CENTS + 1])
def test_invalid_amount(amount):
    with pytest.raises(InvalidPayment):
        validate_amount(amount)


@pytest.mark.parametrize("customer,rail", [("BANCO", "TED"), ("ALUNO", "WIRE")])
def test_invalid_fee_policy(customer, rail):
    with pytest.raises(InvalidPayment):
        calculate_fee(customer, rail, 100)


def test_timestamps_are_stable_across_database_timezones():
    from datetime import datetime, timedelta, timezone
    from dtos.payment_dto import timestamp
    utc = datetime(2026, 9, 22, 18, 30, tzinfo=timezone.utc)
    local = utc.astimezone(timezone(timedelta(hours=-3)))
    assert timestamp(utc) == timestamp(local) == "2026-09-22T18:30:00+00:00"
    assert timestamp(None) is None
