from fastapi import FastAPI, Request

from database import clear_context, open_context
from errors.handlers import unexpected_error_response


def register_session_manager_middleware(application: FastAPI) -> None:
    @application.middleware("http")
    async def manage_session(request: Request, call_next):
        context = open_context()
        context.credential_type = getattr(request.state, "credential_type", None)
        context.credential_digest = getattr(request.state, "credential_digest", None)
        try:
            response = await call_next(request)
            if response.status_code >= 400 and context.db_session is not None:
                context.db_session.rollback()
            return response
        except Exception as error:
            if context.db_session is not None:
                context.db_session.rollback()
            return unexpected_error_response(request, error)
        finally:
            try:
                if context.db_session is not None:
                    context.db_session.close()
            finally:
                clear_context()
