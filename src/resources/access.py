from fastapi.responses import JSONResponse

from controllers.access_controller import AccessController
from utils.schema_handler import SchemaHandler


class AccessResource:
    @SchemaHandler.validate("post_credential.json")
    def on_credential(self, customer_key: str, payload: dict) -> JSONResponse:
        return JSONResponse(content=AccessController().issue_credential(customer_key), status_code=201)

    @SchemaHandler.validate("put_banking_access.json")
    def on_configure(self, customer_key: str, payload: dict) -> JSONResponse:
        return JSONResponse(content=AccessController().configure(customer_key, payload))
