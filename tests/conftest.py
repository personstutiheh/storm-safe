import pytest
from storm_safe import api

@pytest.fixture(autouse=True)
def fresh_store():
    api.store.reset()
    yield
    api.store.reset()