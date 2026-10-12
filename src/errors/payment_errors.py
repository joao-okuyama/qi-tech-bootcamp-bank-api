from errors.base_error import QIException


class BankingAccessDenied(QIException):
    code = "QIT003001"

    def __init__(self):
        super().__init__("Forbidden", self.code, 403, "The credential cannot perform this operation.",
                         "Credencial sem permissão para esta operação.")


class InvalidPayment(QIException):
    code = "QIT003002"

    def __init__(self, description):
        super().__init__("Invalid payment", self.code, 422, description, "Operação financeira inválida.")


class InsufficientFunds(QIException):
    code = "QIT003003"

    def __init__(self):
        super().__init__("Insufficient funds", self.code, 409,
                         "The balance must cover the amount and fee.", "Saldo insuficiente para valor e tarifa.")


class PaymentConflict(QIException):
    code = "QIT003004"

    def __init__(self, description):
        super().__init__("Payment conflict", self.code, 409, description, "Conflito na operação financeira.")
