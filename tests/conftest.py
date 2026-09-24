import random

import pytest
from fastapi.testclient import TestClient

from app.db import connect, init_db
from app.main import app, get_db, get_rng


class FixedRng(random.Random):
    """Always returns the same 'random' number, so the noise is predictable in tests."""

    def __init__(self, value: float):
        super().__init__()
        self.value = value

    def random(self) -> float:
        return self.value


@pytest.fixture
def db_path(tmp_path):
    path = tmp_path / "survey.db"
    with connect(path) as conn:
        init_db(conn)
    return path


@pytest.fixture
def conn(db_path):
    c = connect(db_path)
    yield c
    c.close()


@pytest.fixture
def make_client(db_path):
    def _make(rng: random.Random | None = None) -> TestClient:
        def override_db():
            c = connect(db_path)
            try:
                yield c
            finally:
                c.close()

        app.dependency_overrides[get_db] = override_db
        if rng is not None:
            app.dependency_overrides[get_rng] = lambda: rng
        return TestClient(app)

    yield _make
    app.dependency_overrides.clear()
