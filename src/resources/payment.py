from fastapi.responses import JSONResponse

from controllers.payment_controller import PaymentController
from utils.schema_handler import SchemaHandler


class PaymentResource:
    @SchemaHandler.validate("post_transfer.json")
    def on_post(self, payload: dict) -> JSONResponse:
        result, created = PaymentController().create(payload)
        return JSONResponse(content=result, status_code=201 if created else 200)

    def on_get(self, transfer_key: str) -> JSONResponse:
        return JSONResponse(content=PaymentController().get(transfer_key))

    @SchemaHandler.validate("post_transfer_decision.json")
    def on_approve(self, transfer_key: str, payload: dict) -> JSONResponse:
        return JSONResponse(content=PaymentController().decide(transfer_key, approve=True))

    @SchemaHandler.validate("post_transfer_decision.json")
    def on_reject(self, transfer_key: str, payload: dict) -> JSONResponse:
        return JSONResponse(content=PaymentController().decide(transfer_key, approve=False))

    @SchemaHandler.validate("post_transfer_decision.json")
    def on_execute(self, transfer_key: str, payload: dict) -> JSONResponse:
        return JSONResponse(content=PaymentController().execute(transfer_key))

    @SchemaHandler.validate("post_deposit.json")
    def on_deposit(self, account_key: str, payload: dict) -> JSONResponse:
        result, created = PaymentController().deposit(account_key, payload)
        return JSONResponse(content=result, status_code=201 if created else 200)
