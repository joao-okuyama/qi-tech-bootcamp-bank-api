import time

from fastapi import FastAPI, Request

from constants import BYPASS_ENDPOINTS
from utils.logger import get_logger


logger = get_logger(__name__)


def register_request_logger_middleware(application: FastAPI) -> None:
    @application.middleware("http")
    async def log_request(request: Request, call_next):
        if request.url.path in BYPASS_ENDPOINTS:
            return await call_next(request)

        # Filtros podem conter CPF/e-mail; não registrar query, corpo ou cabeçalhos.
        started_at = time.perf_counter()
        logger.info("ENTROU %s %r", request.method, request.url.path)
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - started_at) * 1000
        logger.info("SAIU %s %s %r - %.1f ms", response.status_code,
                    request.method, request.url.path, elapsed_ms)
        return response
