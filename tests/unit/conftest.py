import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg2://unit:unit@127.0.0.1:1/unit")
os.environ.setdefault("INTERNAL_TOKEN", "unit-test-token")


@pytest.fixture(autouse=True)
def session(monkeypatch):
    import database

    session = MagicMock()
    monkeypatch.setattr(database, "SessionLocal", MagicMock(return_value=session))
    context = database.open_context()
    context.db_session = session
    yield session
    database.clear_context()
