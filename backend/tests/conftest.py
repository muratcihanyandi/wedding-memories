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
def client(tmp_path, monkeypatch):
    """Uygulamayi test ortami env'i ile olusturur.

    Cookie'ler TestClient uzerinde otomatik yonetilir; upload testlerinde
    ayni client ile coklu oturum gerekiyorsa cookie header'i elle verilir.
    """
    upload_root = tmp_path / "uploads"
    upload_root.mkdir()
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("UPLOAD_ROOT", str(upload_root))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(tmp_path / 'app.sqlite3').as_posix()}")
    monkeypatch.setenv("REQUIRE_STORAGE_MARKER", "false")
    monkeypatch.setenv("SESSION_SECRET", "test-secret")
    monkeypatch.setenv("ADMIN_USERNAME", ADMIN_USER)
    monkeypatch.setenv("ADMIN_PASSWORD_HASH", hash_password(ADMIN_PASS))
    monkeypatch.setenv("LOGIN_MAX_FAILURES", "5")
    monkeypatch.setenv("LOGIN_WINDOW_MINUTES", "15")
    reset_settings()

    from app.main import create_app

    app = create_app()
    with TestClient(app) as test_client:
        test_client.upload_root = upload_root
        yield test_client

    if app_db._engine is not None:
        app_db._engine.dispose()
        app_db._engine = None
        app_db._SessionLocal = None
    reset_settings()
