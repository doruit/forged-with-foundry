"""Repository-wide test isolation.

Some control modules call ``load_dotenv(infra/.env)`` when they are imported,
which happens during test collection. On a maintainer machine that leaks real
Azure settings into every later test, so a local ``pytest -q`` behaves
differently from CI (which has no .env). Each test starts from the environment
captured before any control module was collected.
"""

import os

import pytest

_BASELINE = dict(os.environ)


def _restore() -> None:
    for key in list(os.environ):
        if key not in _BASELINE and not key.startswith("PYTEST_"):
            del os.environ[key]
    os.environ.update(_BASELINE)


@pytest.fixture(autouse=True)
def _environment_as_before_collection():
    _restore()
    yield
    _restore()
