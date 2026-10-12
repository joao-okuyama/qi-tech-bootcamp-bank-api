from os import environ


INTERNAL_TOKEN = environ.get("INTERNAL_TOKEN", "default_token")


class RequestGenerator:
    """Gerador base de requisições de teste."""
    pass
