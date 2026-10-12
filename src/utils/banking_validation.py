import re
import unicodedata
from datetime import date
from uuid import UUID

from errors import InvalidParameter
from errors.banking_errors import InvalidBankingRegistration
from utils.document_number import is_valid_cpf


def clean_registration_text(value: str, field: str) -> str:
    for character in value:
        if unicodedata.category(character) in ("Cc", "Cs") or character in "\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069":
            raise InvalidBankingRegistration(f"The {field} contains unsupported control characters.")
    value = unicodedata.normalize("NFC", value).strip()
    if not value:
        raise InvalidBankingRegistration(f"The {field} must not be blank.")
    if len(value) > 255:
        raise InvalidBankingRegistration(f"The normalized {field} must not exceed 255 characters.")
    return value


def parse_key(value: str) -> UUID:
    try:
        return UUID(value)
    except (ValueError, AttributeError, TypeError):
        raise InvalidParameter("The key must be a UUID.") from None


def validate_birthdate(value: str) -> date:
    try:
        birthdate = date.fromisoformat(value)
    except ValueError:
        raise InvalidBankingRegistration("The birthdate must be a real calendar date.") from None
    if birthdate > date.today():
        raise InvalidBankingRegistration("The birthdate cannot be in the future.")
    return birthdate


def validate_cpf(value: str) -> None:
    if not re.fullmatch(r"[0-9]{11}", value) or not is_valid_cpf(value):
        raise InvalidBankingRegistration("The CPF check digits are invalid.")


def is_valid_cnpj(value: str) -> bool:
    if not re.fullmatch(r"[A-Z0-9]{12}[0-9]{2}", value) or len(set(value)) == 1:
        return False
    numbers = [ord(character) - 48 for character in value[:12]]
    for weights in ([5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2], [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]):
        remainder = sum(number * weight for number, weight in zip(numbers, weights)) % 11
        digit = 0 if remainder < 2 else 11 - remainder
        if digit != int(value[len(numbers)]):
            return False
        numbers.append(digit)
    return True
