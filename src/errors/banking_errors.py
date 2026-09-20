from errors.base_error import QIException


class BankingEntityNotFound(QIException):
    code = "QIT002001"

    def __init__(self, entity: str):
        super().__init__(
            "Entity not found", self.code, 404,
            f"The requested {entity} was not found.",
            "O cadastro solicitado não foi encontrado.",
        )


class BankingRegistrationConflict(QIException):
    code = "QIT002002"

    def __init__(self, field: str):
        super().__init__(
            "Registration conflict", self.code, 409,
            f"A registration already exists for this {field}.",
            "Já existe um cadastro para o identificador informado.",
        )


class InvalidBankingRegistration(QIException):
    code = "QIT002003"

    def __init__(self, description: str):
        super().__init__(
            "Invalid registration", self.code, 422, description,
            "Os dados do cadastro não são válidos.",
        )


class CustomerCannotOpenAccount(QIException):
    code = "QIT002004"

    def __init__(self):
        super().__init__(
            "Customer cannot open account", self.code, 409,
            "The customer must be active and have a matching student or organization registration.",
            "O cliente precisa estar ativo e ter um cadastro compatível.",
        )
