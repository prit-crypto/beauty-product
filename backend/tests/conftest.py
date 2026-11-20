import os

import pytest

os.environ["AI_PROVIDER"] = "rule"  # tests never depend on the local .env choice
os.environ["AI_REWRITE"] = "true"
os.environ.setdefault("ADMIN_PASSWORD", "test-pw")


@pytest.fixture()
def client(tmp_path):
    from fastapi.testclient import TestClient

    from app import store
    from app.main import app
    from app.providers import factory

    store.reset_for_tests(str(tmp_path / "test.db"))
    factory.set_override(None)
    return TestClient(app)
