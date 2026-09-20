from datetime import date, timedelta
from uuid import uuid4

import pytest

from errors import InvalidParameter
from errors.banking_errors import InvalidBankingRegistration
from utils.banking_validation import is_valid_cnpj, parse_key, validate_birthdate, validate_cpf


@pytest.mark.parametrize("value", ["11222333000181", "12ABC34501DE35", "00000000E08G12"])
def test_accepts_cnpj_with_valid_check_digits(value):
    assert is_valid_cnpj(value)


@pytest.mark.parametrize("value", ["00000000000000", "11222333000182", "12ABC34501DE36",
                                  "12abc34501DE35", "11.222.333/0001-81", ""])
def test_rejects_invalid_cnpj(value):
    assert not is_valid_cnpj(value)


def test_accepts_cpf():
    validate_cpf("52998224725")


@pytest.mark.parametrize("value", ["00000000000", "52998224726", "529.982.247-25"])
def test_rejects_invalid_cpf(value):
    with pytest.raises(InvalidBankingRegistration):
        validate_cpf(value)


@pytest.mark.parametrize("value", ["2026-02-30", "2026-13-01", "not-a-date"])
def test_rejects_impossible_birthdate(value):
    with pytest.raises(InvalidBankingRegistration):
        validate_birthdate(value)


def test_rejects_future_birthdate():
    with pytest.raises(InvalidBankingRegistration):
        validate_birthdate((date.today() + timedelta(days=1)).isoformat())


def test_accepts_real_birthdate_without_inventing_age_policy():
    assert validate_birthdate("2008-02-29") == date(2008, 2, 29)


def test_uuid_parsing():
    key = uuid4()
    assert parse_key(str(key)) == key
    with pytest.raises(InvalidParameter):
        parse_key("not-a-key")
