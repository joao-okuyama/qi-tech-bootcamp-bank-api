from fastapi.responses import JSONResponse

from controllers.customer_controller import CustomerController
from utils.schema_handler import SchemaHandler


class CustomerResource:
    @SchemaHandler.validate("post_student.json")
    def on_post_student(self, payload: dict) -> JSONResponse:
        result = CustomerController().create_student(payload)
        return JSONResponse(content=result, status_code=201)

    @SchemaHandler.validate("post_student_organization.json")
    def on_post_organization(self, payload: dict) -> JSONResponse:
        result = CustomerController().create_organization(payload)
        return JSONResponse(content=result, status_code=201)

    def on_get_by_key(self, customer_key: str) -> JSONResponse:
        result = CustomerController().get_by_key(customer_key)
        return JSONResponse(content=result, status_code=200)
