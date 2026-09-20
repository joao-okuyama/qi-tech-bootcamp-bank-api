from fastapi.responses import JSONResponse

from controllers.university_controller import UniversityController
from utils.schema_handler import SchemaHandler


class UniversityResource:
    @SchemaHandler.validate("post_university.json")
    def on_post(self, payload: dict) -> JSONResponse:
        result = UniversityController().create(payload)
        return JSONResponse(content=result, status_code=201)

    def on_get_by_key(self, university_key: str) -> JSONResponse:
        result = UniversityController().get_by_key(university_key)
        return JSONResponse(content=result, status_code=200)
