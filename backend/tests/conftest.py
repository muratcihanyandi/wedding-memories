"""Test ortami - her test kendi gecici sqlite + upload klasorunu kullanir."""

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import pytest  # noqa: E402

from app import db as app_db  # noqa: E402


@pytest.fixture()
def db_engine(tmp_path):
    engine = app_db.init_engine(f"sqlite:///{(tmp_path / 'test.sqlite3').as_posix()}")
    app_db.create_all()
    yield engine
    engine.dispose()
    app_db._engine = None
    app_db._SessionLocal = None
