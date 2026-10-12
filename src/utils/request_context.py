import re
import uuid
from contextvars import ContextVar


REQUEST_ID_HEADER = "X-Request-ID"
SAFE_REQUEST_ID = re.compile(r"[A-Za-z0-9_-]{1,64}")
NO_REQUEST_ID = "-"
_request_id = ContextVar("request_id", default=NO_REQUEST_ID)


def get_request_id():
    return _request_id.get()


def set_request_id(request_id):
    return _request_id.set(request_id)


def reset_request_id(token):
    _request_id.reset(token)


def build_request_id(received_request_id=None):
    if received_request_id is not None and SAFE_REQUEST_ID.fullmatch(received_request_id):
        return received_request_id
    return str(uuid.uuid4())
