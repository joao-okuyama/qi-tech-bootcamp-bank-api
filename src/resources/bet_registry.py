from fastapi.responses import JSONResponse

from controllers.bet_registry_controller import BetRegistryController
from utils.schema_handler import SchemaHandler


class BetRegistryResource:
    @SchemaHandler.validate("post_bet_registry_sync.json")
    def on_sync(self, payload: dict):
        return JSONResponse(content=BetRegistryController().sync(payload), status_code=200)
