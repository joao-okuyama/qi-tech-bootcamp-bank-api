from fastapi import FastAPI

from constants import check_variables
from errors import register_error_handlers
from errors.base_error import error_verification
from middlewares import (
    register_internal_token_middleware,
    register_request_context_middleware,
    register_request_logger_middleware,
    register_session_manager_middleware,
)
from resources import HealthCheckResource, SampleEntityResource
from resources.access import AccessResource
from resources.account import AccountResource
from resources.customer import CustomerResource
from resources.payment import PaymentResource
from resources.university import UniversityResource
from utils.logger import setup_logging


def create_app() -> FastAPI:
    application = FastAPI(
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    # O último middleware registrado executa primeiro: contexto, log, credencial, sessão.
    register_session_manager_middleware(application)
    register_internal_token_middleware(application)
    register_request_logger_middleware(application)
    register_request_context_middleware(application)

    health_check_resource = HealthCheckResource()
    sample_entity_resource = SampleEntityResource()

    application.add_api_route("/", health_check_resource.on_get_home, methods=["GET"])
    application.add_api_route(
        "/health_check",
        health_check_resource.on_get_health_check,
        methods=["GET"]
    )

    application.add_api_route(
        "/sample_entity",
        sample_entity_resource.on_post,
        methods=["POST"],
    )
    application.add_api_route(
        "/sample_entity/{sample_entity_key}",
        sample_entity_resource.on_get_by_key,
        methods=["GET"],
    )
    application.add_api_route(
        "/sample_entity/{sample_entity_key}",
        sample_entity_resource.on_put_by_key,
        methods=["PUT"],
    )
    application.add_api_route(
        "/webhook/sample_entity/{sample_entity_key}/increment_counter",
        sample_entity_resource.on_put_increment_counter,
        methods=["PUT"],
    )
    application.add_api_route(
        "/sample_entities",
        sample_entity_resource.on_get_list,
        methods=["GET"],
    )

    university_resource = UniversityResource()
    customer_resource = CustomerResource()
    account_resource = AccountResource()

    application.add_api_route(
        "/university", university_resource.on_post, methods=["POST"],
    )
    application.add_api_route(
        "/university/{university_key}", university_resource.on_get_by_key, methods=["GET"],
    )
    application.add_api_route(
        "/student", customer_resource.on_post_student, methods=["POST"],
    )
    application.add_api_route(
        "/student_organization", customer_resource.on_post_organization, methods=["POST"],
    )
    application.add_api_route(
        "/customer/{customer_key}", customer_resource.on_get_by_key, methods=["GET"],
    )
    application.add_api_route(
        "/customer/{customer_key}/account", account_resource.on_post, methods=["POST"],
    )
    application.add_api_route(
        "/account/{account_key}", account_resource.on_get_by_key, methods=["GET"],
    )
    application.add_api_route(
        "/account/{account_key}/balance", account_resource.on_get_balance, methods=["GET"],
    )
    application.add_api_route(
        "/account/{account_key}/statement", account_resource.on_get_statement, methods=["GET"],
    )

    access_resource = AccessResource()
    payment_resource = PaymentResource()
    application.add_api_route("/customer/{customer_key}/credential", access_resource.on_credential, methods=["POST"])
    application.add_api_route("/customer/{customer_key}/banking_access", access_resource.on_configure, methods=["PUT"])
    application.add_api_route("/account/{account_key}/deposit", payment_resource.on_deposit, methods=["POST"])
    application.add_api_route("/transfer", payment_resource.on_post, methods=["POST"])
    application.add_api_route("/transfer/{transfer_key}", payment_resource.on_get, methods=["GET"])
    application.add_api_route("/transfer/{transfer_key}/approve", payment_resource.on_approve, methods=["POST"])
    application.add_api_route("/transfer/{transfer_key}/reject", payment_resource.on_reject, methods=["POST"])
    application.add_api_route("/transfer/{transfer_key}/execute", payment_resource.on_execute, methods=["POST"])

    register_error_handlers(application)

    return application


def main() -> FastAPI:
    check_variables()
    error_verification()
    setup_logging()

    return create_app()


app = main()
