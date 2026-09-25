import pytest

from tests.utils.db_utils import DbUtils


@pytest.fixture(scope="session", autouse=True)
def dedicated_test_database():
    DbUtils.database_url()
