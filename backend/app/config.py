"""Uygulama ayarlari - tum degerler ortam degiskenlerinden okunur.

Gelistirmede varsayilanlar local diskteki ./data klasorunu kullanir.
Uretimde docker-compose .env uzerinden /app/data/... yollarini verir.
"""

import os
from dataclasses import dataclass
from pathlib import Path

_TRUE = ("1", "true", "yes", "on")


def _env_str(name: str, default: str = "") -> str:
    value = os.environ.get(name)
    return value if value not in (None, "") else default


def _env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    return value.strip().lower() in _TRUE


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, "") or default)
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    app_env: str
    database_url: str
    upload_root: Path
    max_upload_size_mb: int
    admin_username: str
    admin_password_hash: str
    session_secret: str
    public_url: str
    cookie_secure: bool
    trust_proxy: bool
    require_storage_marker: bool
    login_max_failures: int
    login_window_minutes: int
    upload_max_per_hour: int

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @classmethod
    def from_env(cls) -> "Settings":
        data_dir = Path("./data")
        return cls(
            app_env=_env_str("APP_ENV", "production"),
            database_url=_env_str(
                "DATABASE_URL", f"sqlite:///{(data_dir / 'db' / 'wedding.sqlite3').as_posix()}"
            ),
            upload_root=Path(_env_str("UPLOAD_ROOT", str(data_dir / "uploads"))),
            max_upload_size_mb=_env_int("MAX_UPLOAD_SIZE_MB", 2048),
            admin_username=_env_str("ADMIN_USERNAME", "admin"),
            admin_password_hash=_env_str("ADMIN_PASSWORD_HASH", ""),
            session_secret=_env_str("SESSION_SECRET", ""),
            public_url=_env_str("PUBLIC_URL", ""),
            cookie_secure=_env_bool("COOKIE_SECURE", False),
            trust_proxy=_env_bool("TRUST_PROXY", False),
            require_storage_marker=_env_bool("REQUIRE_STORAGE_MARKER", True),
            login_max_failures=_env_int("LOGIN_MAX_FAILURES", 5),
            login_window_minutes=_env_int("LOGIN_WINDOW_MINUTES", 15),
            upload_max_per_hour=_env_int("UPLOAD_MAX_PER_HOUR", 120),
        )


_cached_settings: Settings | None = None


def get_settings() -> Settings:
    global _cached_settings
    if _cached_settings is None:
        _cached_settings = Settings.from_env()
    return _cached_settings


def reset_settings() -> None:
    """Test yardimcisi: bir sonraki get_settings cagrisinda env'i yeniden okur."""
    global _cached_settings
    _cached_settings = None
