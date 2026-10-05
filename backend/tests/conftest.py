"""Test ortami - her test kendi gecici sqlite + upload klasorunu kullanir."""

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import db as app_db  # noqa: E402
from app.config import reset_settings  # noqa: E402
from app.security import hash_password  # noqa: E402

ADMIN_USER = "admin"
ADMIN_PASS = "guclu-sifre-123"


@pytest.fixture()
def db_engine(tmp_path):
    engine = app_db.init_engine(f"sqlite:///{(tmp_path / 'test.sqlite3').as_posix()}")
    app_db.create_all()
    yield engine
    engine.dispose()
    app_db._engine = None
    app_db._SessionLocal = None


@pytest.fixture()
def client_factory(tmp_path, monkeypatch):
    """Ortam degiskeni override'iyla uygulama ureten fabrika.

    client_factory(MAX_UPLOAD_SIZE_MB="1") gibi cagrilarak testlere ozel
    ayarlar verilebilir.
    """
    created = []
    counter = {"n": 0}

    def _make(**overrides):
        counter["n"] += 1
        n = counter["n"]
        upload_root = tmp_path / f"uploads_{n}"
        upload_root.mkdir()

        env = {
            "APP_ENV": "development",
            "UPLOAD_ROOT": str(upload_root),
            "DATABASE_URL": f"sqlite:///{(tmp_path / ('app_%d.sqlite3' % n)).as_posix()}",
            "REQUIRE_STORAGE_MARKER": "false",
            "SESSION_SECRET": "test-secret",
            "ADMIN_USERNAME": ADMIN_USER,
            "ADMIN_PASSWORD_HASH": hash_password(ADMIN_PASS),
            "LOGIN_MAX_FAILURES": "5",
            "LOGIN_WINDOW_MINUTES": "15",
        }
        env.update({k: str(v) for k, v in overrides.items()})
        for key, value in env.items():
            monkeypatch.setenv(key, value)
        reset_settings()

        from app.main import create_app

        app = create_app()
        test_client = TestClient(app)
        test_client.upload_root = upload_root
        created.append((app, test_client))
        return test_client

    yield _make

    for app, test_client in created:
        test_client.close()
    if app_db._engine is not None:
        app_db._engine.dispose()
        app_db._engine = None
        app_db._SessionLocal = None
    reset_settings()


@pytest.fixture()
def client(client_factory):
    return client_factory()
