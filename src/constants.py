import os


SERVICE_ROOT = os.path.abspath(os.path.dirname(__file__))

SCHEMA_PATH = os.path.join(SERVICE_ROOT, "schemas")

APP_ENV = os.environ.get("APP_ENV", "local")
SERVICE_NAME = os.environ.get("SERVICE_NAME", "banco-universitario-api")

DATABASE_URL = os.environ.get("DATABASE_URL")
INTERNAL_TOKEN = os.environ.get("INTERNAL_TOKEN")
BET_REGISTRY_URL = os.environ.get(
    "BET_REGISTRY_URL",
    "https://www.gov.br/fazenda/pt-br/composicao/orgaos/secretaria-de-premios-e-apostas/"
    "transparencia-ativa-processos-de-autorizacao-de-apostas-de-quota-fixa/planilha-de-autorizacoes-1.csv",
)
BET_REGISTRY_TIMEOUT = int(os.environ.get("BET_REGISTRY_TIMEOUT", "20"))
BET_REGISTRY_MAX_BYTES = int(os.environ.get("BET_REGISTRY_MAX_BYTES", str(2 * 1024 * 1024)))
BET_REGISTRY_MAX_AGE_HOURS = int(os.environ.get("BET_REGISTRY_MAX_AGE_HOURS", "48"))

BYPASS_ENDPOINTS = [
    "/",
    "/health_check",
]

REQUIRED_VARIABLES = ["DATABASE_URL", "INTERNAL_TOKEN"]


def check_variables():
    if any(value <= 0 for value in (BET_REGISTRY_TIMEOUT, BET_REGISTRY_MAX_BYTES, BET_REGISTRY_MAX_AGE_HOURS)):
        raise EnvironmentError("Os limites do cadastro BET devem ser positivos.")
    missing = []
    for name in REQUIRED_VARIABLES:
        if not globals().get(name):
            missing.append(name)

    if missing:
        raise EnvironmentError(
            f"Faltam variáveis de ambiente: {', '.join(missing)}. "
            "Rodando com 'docker compose up' elas já vêm preenchidas. "
            "Fora do Docker, copie o .env.example para .env."
        )
    if not INTERNAL_TOKEN.strip():
        raise EnvironmentError("INTERNAL_TOKEN não pode ser vazio ou conter apenas espaços.")
    if APP_ENV.lower() not in ("local", "test") and INTERNAL_TOKEN == "default_token":
        raise EnvironmentError("Configure um INTERNAL_TOKEN próprio fora dos ambientes local e test.")
