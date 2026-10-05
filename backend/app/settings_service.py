"""Admin panelinden duzenleneb uygulama ayarlari (settings tablosu).

Tum metinler buradan yonetilir; boylece dugun sahibi icerigi kod
degistirmeden ozellestirebilir (spec #43).
"""

from sqlalchemy.orm import Session

from .models import Setting

DEFAULTS = {
    "wedding_title": "Elif & Erhan",
    "welcome_text": "Bu güzel günün anılarını bizimle paylaşın. 🤍",
    "upload_welcome_text": "Bu geceden kalan güzel anılarını bizimle paylaş.",
    "success_text": "Anıların başarıyla kaydedildi! 🤍",
}

EDITABLE_KEYS = list(DEFAULTS.keys())


def get_setting(db: Session, key: str) -> str:
    row = db.get(Setting, key)
    if row is not None and row.value != "":
        return row.value
    return DEFAULTS.get(key, "")


def set_setting(db: Session, key: str, value: str) -> None:
    row = db.get(Setting, key)
    if row is None:
        db.add(Setting(key=key, value=value))
    else:
        row.value = value


def get_public_config(db: Session, max_upload_mb: int) -> dict:
    return {
        "wedding_title": get_setting(db, "wedding_title"),
        "welcome_text": get_setting(db, "welcome_text"),
        "upload_welcome_text": get_setting(db, "upload_welcome_text"),
        "success_text": get_setting(db, "success_text"),
        "max_upload_mb": max_upload_mb,
    }
