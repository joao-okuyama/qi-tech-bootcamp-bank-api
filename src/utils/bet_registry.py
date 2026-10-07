import csv
import io
import re
import unicodedata

from utils.banking_validation import clean_registration_text, is_valid_cnpj


CNPJ_PATTERN = re.compile(r"[A-Z0-9]{12}[0-9]{2}")


def normalize_cnpj(value):
    value = re.sub(r"[./\-\s]", "", value).upper()
    if not CNPJ_PATTERN.fullmatch(value) or not is_valid_cnpj(value):
        raise ValueError("Invalid company CNPJ.")
    return value


def parse_bet_registry(content):
    text = content.decode("utf-8-sig") if isinstance(content, bytes) else content.lstrip("\ufeff")
    reader = csv.reader(io.StringIO(text, newline=""), delimiter=";", strict=True)
    companies = {}
    header_seen = False
    expected_item = 1
    for row in reader:
        if not row or not any(field.strip() for field in row):
            continue
        if not header_seen:
            if len(row) >= 4 and row[3].strip().upper() == "CNPJ":
                if "DENOMINA" not in row[2].upper():
                    raise ValueError("Unexpected company-name header.")
                header_seen = True
            continue
        item = row[0].strip()
        if not item:
            # Marcas e anotacoes de portarias continuam sem nome/CNPJ de outra empresa.
            if (any(field.strip() for field in row[2:4])
                    or (row[1].strip() and not row[1].strip().startswith("("))):
                raise ValueError("Incomplete company row.")
            continue
        if not item.isdecimal() or int(item) != expected_item or len(row) < 4:
            raise ValueError("Missing or malformed company row.")
        expected_item += 1
        name = unicodedata.normalize("NFC", row[2]).strip()
        if not name or len(name) > 255:
            raise ValueError("Missing or oversized corporate name.")
        name = clean_registration_text(name, "razao_social")
        cnpj = normalize_cnpj(row[3])
        if cnpj in companies and companies[cnpj]["razao_social"] != name:
            raise ValueError("Conflicting names for the same CNPJ.")
        companies[cnpj] = {"cnpj": cnpj, "razao_social": name}
    if not header_seen or not companies:
        raise ValueError("No companies found in the official CSV layout.")
    return list(companies.values())
