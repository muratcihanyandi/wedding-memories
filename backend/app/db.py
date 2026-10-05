"""SQLAlchemy engine ve session yonetimi.

init_engine() uygulama acilisinda bir kez cagirilir; testler kendi
gecici sqlite dosyalariyla cagirir. SQLite icin WAL modu acilir:
ayni anda okuyan admin paneli ile yazan upload istekleri bloklanmaz.
"""

from pathlib import Path

from fastapi import Depends
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from .models import Base

_engine = None
_SessionLocal: sessionmaker | None = None


def init_engine(database_url: str):
    """Engine'i olusturur.

    - SQLite URL'lerinde db klasoru otomatik acilir (WAL modu ile).
    - Duz 'postgresql://' URL'leri SQLAlchemy'in psycopg (v3) surucusune
      cevrilir; boylece standart baglanti dizisi dogrudan kullanilabilir.
    """
    global _engine, _SessionLocal

    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)

    if database_url.startswith("sqlite:///"):
        db_path = database_url.replace("sqlite:///", "", 1)
        if db_path and db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    connect_args = {}
    if database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    _engine = create_engine(database_url, connect_args=connect_args, pool_pre_ping=True)

    if database_url.startswith("sqlite"):

        @event.listens_for(_engine, "connect")
        def _sqlite_pragmas(dbapi_conn, _record):  # pragma: no cover
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    _SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False)
    return _engine


def get_engine():
    if _engine is None:
        raise RuntimeError("init_engine() henüz çağrılmadı")
    return _engine


def create_all() -> None:
    Base.metadata.create_all(get_engine())


def get_db() -> Session:
    """FastAPI dependency - transaction yonetimi route'larda yapilir."""
    if _SessionLocal is None:
        raise RuntimeError("init_engine() henüz çağrılmadı")
    db = _SessionLocal()
    try:
        yield db
    finally:
        db.close()


DbDep = Depends(get_db)
