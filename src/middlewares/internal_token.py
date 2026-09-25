from hmac import compare_digest
from hashlib import sha256

from fastapi import FastAPI, Request

from constants import BYPASS_ENDPOINTS, INTERNAL_TOKEN
from errors.base_error import ForbiddenNotInternal
from errors.handlers import qi_exception_to_response


def register_internal_token_middleware(application: FastAPI) -> None:
    """Distingue acesso administrativo de operações autenticadas de aluno.

    O valor certo vem da variável de ambiente INTERNAL_TOKEN, nunca do
    código. As rotas de BYPASS_ENDPOINTS (raiz e health check) são públicas.
    Bearer identifica uma credencial de aluno; o controller valida a identidade
    no banco e decide se ela pode executar a operação solicitada.

    Repare que aqui a gente DEVOLVE a resposta de erro em vez de levantar
    a exceção: dentro de um middleware, ninguém está escutando pra traduzir
    o erro — quem traduz são os exception handlers, que rodam mais pra
    dentro. Levantar aqui viraria um 500.
    """

    @application.middleware("http")
    async def check_internal_token(request: Request, call_next):
        is_public = request.url.path in BYPASS_ENDPOINTS

        if is_public:
            return await call_next(request)

        authorizations = request.headers.getlist("Authorization")
        tokens = request.headers.getlist("INTERNAL-TOKEN")
        if authorizations:
            if len(authorizations) != 1 or tokens:
                return qi_exception_to_response(ForbiddenNotInternal())
            scheme, separator, token = authorizations[0].partition(" ")
            if scheme != "Bearer" or separator != " " or not 32 <= len(token) <= 128:
                return qi_exception_to_response(ForbiddenNotInternal())
            request.state.credential_type = "BEARER"
            request.state.credential_digest = sha256(token.encode("utf-8")).hexdigest()
            return await call_next(request)

        if len(tokens) != 1 or not compare_digest(tokens[0].encode("utf-8"), INTERNAL_TOKEN.encode("utf-8")):
            return qi_exception_to_response(ForbiddenNotInternal())

        request.state.credential_type = "INTERNAL"
        request.state.credential_digest = None
        return await call_next(request)
