import pytest
from fastapi.testclient import TestClient

from app import create_app
from constants import INTERNAL_TOKEN
from database import clear_context, get_context, open_context
from utils.request_context import get_request_id, reset_request_id, set_request_id


def test_nested_work_restores_the_previous_database_context(session):
    outer = get_context()
    inner = open_context()
    assert get_context() is inner
    clear_context(inner)
    assert get_context() is outer


def test_request_id_restores_outer_value_even_when_request_fails():
    token = set_request_id("outer-work")
    try:
        with TestClient(create_app()) as client:
            response = client.get("/missing", headers={"X-Request-ID": "failed-request"})
            assert response.headers["X-Request-ID"] == "failed-request"
            next_response = client.get("/health_check", headers={"X-Request-ID": "next-request"})
            assert next_response.headers["X-Request-ID"] == "next-request"
        assert get_request_id() == "outer-work"
    finally:
        reset_request_id(token)
