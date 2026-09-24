from errors.payment_errors import InvalidPayment


MAX_CENTS = 2**63 - 1
PJ_TED_RATE_BPS = 100
PJ_TED_CAP_CENTS = 999


def validate_amount(value):
    if type(value) is not int or not 0 < value <= MAX_CENTS:
        raise InvalidPayment("amount_cents must be a positive BIGINT integer.")
    return value


def calculate_fee(customer_type, transfer_type, amount):
    validate_amount(amount)
    if customer_type not in ("ALUNO", "ORGANIZACAO_ESTUDANTIL") or transfer_type not in ("PIX", "TED"):
        raise InvalidPayment("Unsupported customer or transfer type.")
    if customer_type == "ALUNO" or transfer_type == "PIX":
        return 0
    return min((amount * PJ_TED_RATE_BPS + 5000) // 10000, PJ_TED_CAP_CENTS)
