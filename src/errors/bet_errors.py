from errors.base_error import QIException


class BetRegistryUnavailable(QIException):
    code = "QIT004001"

    def __init__(self):
        super().__init__("Bet registry unavailable", self.code, 503,
                         "The company registry is missing or expired. Please try again later.",
                         "Cadastro de empresas indisponivel. Tente novamente mais tarde.")


class BetRegistryInvalid(QIException):
    code = "QIT004002"

    def __init__(self, description="The downloaded registry is invalid. The previous snapshot was preserved."):
        super().__init__("Invalid bet registry", self.code, 422, description,
                         "Cadastro invalido. A lista anterior foi preservada.")


class BetRegistryReviewRequired(QIException):
    code = "QIT004003"

    def __init__(self, digest, removed):
        super().__init__("Registry review required", self.code, 409,
                         f"The snapshot removes {removed} companies. Review it and submit reviewed_sha256={digest}.",
                         "A remocao de empresas exige revisao do conteudo baixado.")


class BettingTransferBlocked(QIException):
    code = "QIT004004"

    def __init__(self):
        super().__init__("Transfer blocked", self.code, 403,
                         "Transfers to companies in the betting registry are not allowed. No funds were moved.",
                         "Transferencia para empresa de apostas bloqueada. Nenhum valor foi movimentado.")
