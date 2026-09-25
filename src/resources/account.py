from fastapi import Request
from fastapi.responses import JSONResponse

from controllers.account_controller import AccountController
from utils.schema_handler import SchemaHandler


class AccountResource:
    @SchemaHandler.validate("post_account.json")
    def on_post(self, customer_key: str, payload: dict) -> JSONResponse:
        result = AccountController().create(customer_key)
        return JSONResponse(content=result, status_code=201)

    def on_get_by_key(self, account_key: str) -> JSONResponse:
        result = AccountController().get_by_key(account_key)
        return JSONResponse(content=result, status_code=200)

    def on_get_balance(self, account_key: str) -> JSONResponse:
        result = AccountController().get_balance(account_key)
        return JSONResponse(content=result, status_code=200)

    @SchemaHandler.validate_query_params("get_account_statement.json")
    def on_get_statement(self, account_key: str, request: Request) -> JSONResponse:
        limit = int(request.query_params.get("limit", 20))
        page = int(request.query_params.get("page", 0))
        cursor = request.query_params.get("cursor")
        controller = AccountController()
        if cursor:
            result = controller.get_statement_cursor(account_key, limit, cursor)
            result.update({"limit": limit, "cursor": cursor})
        else:
            result = controller.get_statement(account_key, limit, page * limit)
            result.update({"limit": limit, "page": page})
        return JSONResponse(content=result, status_code=200)
