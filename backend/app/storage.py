"""Dosya sistemi guvenlik katmani.

Kullanicidan gelen hicbir isim/degisken dogrudan filesystem yolunda
kullanilmaz. Butun yollar safe_join uzerinden kurulur ve resolve()
sonrasi kok disina cikis ValueError ile engellenir.
"""

import os
import re
import shutil
import unicodedata
from dataclasses import dataclass
from pathlib import Path

MARKER_NAME = ".wedding-storage"

MAX_DISPLAY_NAME_LEN = 40
MAX_FILENAME_LEN = 100

# Turkce ozel harfler NFKD ile ayrismaz, elle eslenir.
_TR_MAP = str.maketrans({
    "ı": "i", "İ": "I", "ş": "s", "Ş": "S", "ğ": "g", "Ğ": "G",
    "ç": "c", "Ç": "C", "ö": "o", "Ö": "O", "ü": "u", "Ü": "U",
    "â": "a", "Â": "A", "î": "i", "Î": "I", "û": "u", "Û": "U",
})

_ALLOWED_FILENAME_RE = re.compile(r"[^A-Za-z0-9._ \-]")
_ALLOWED_FOLDER_RE = re.compile(r"[^A-Za-z0-9 \-]")


def _transliterate(text: str) -> str:
    text = text.translate(_TR_MAP)
    text = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def sanitize_display_name(raw: str) -> str:
    """Gorunen isimden guvenli klasor adi uretir.

    - Turkce harfler ASCII'ye cevrilir (klasor isimleri ASCII kalmali)
    - Tehlikeli karakterler boslukla degistirilir, bosluklar kasilir
    - Sonuc bosalirsa 'Misafir' doner
    """
    if not raw:
        return "Misafir"
    text = _transliterate(raw)
    text = _ALLOWED_FOLDER_RE.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = text[:MAX_DISPLAY_NAME_LEN].strip()
    if not text or text.strip("-") == "":
        return "Misafir"
    return text


def unique_folder_name(base: str, existing: set[str]) -> str:
    """Cakisma durumunda Erhan -> Erhan-2 -> Erhan-3."""
    if base not in existing:
        return base
    for i in range(2, 1000):
        candidate = f"{base}-{i}"
        if candidate not in existing:
            return candidate
    raise ValueError("Klasör adı tükenemedi")  # pragma: no cover


def sanitize_filename(raw: str) -> str:
    """Dosya adini guvenli hale getirir - path bileşenleri ve gizli dosya
    karakterleri temizlenir, Turkce harfler ASCII'ye cevrilir."""
    name = (raw or "").replace("\\", "/").split("/")[-1]
    name = _transliterate(name)
    name = name.replace("\x00", "")
    name = _ALLOWED_FILENAME_RE.sub("_", name)
    name = name.strip(" .")
    if not name:
        name = "dosya"
    if name.startswith("."):
        name = "_" + name
    if len(name) > MAX_FILENAME_LEN:
        stem, dot, ext = name.rpartition(".")
        if dot and len(ext) <= 10:
            name = stem[: MAX_FILENAME_LEN - len(ext) - 1] + "." + ext
        else:
            name = name[:MAX_FILENAME_LEN]
    return name


def unique_filename(base: str, existing: set[str]) -> str:
    if base not in existing:
        return base
    stem, dot, ext = base.rpartition(".")
    if not dot:
        stem, ext = base, ""
    else:
        ext = "." + ext
    for i in range(2, 10000):
        candidate = f"{stem}_{i}{ext}"
        if candidate not in existing:
            return candidate
    raise ValueError("Dosya adı tükenemedi")  # pragma: no cover


def safe_join(root: Path, *parts: str) -> Path:
    """root icinde kalan guvenli yol uretir; disari cikarsa ValueError.

    Path traversal (../../x) ve absolute path enjeksiyonlari burada
    yakalanir. Butun dosya islemleri bu fonksiyondan gecmelidir.
    """
    root_resolved = root.resolve()
    candidate = root_resolved.joinpath(*[p for p in parts if p])
    resolved = candidate.resolve()
    if not resolved.is_relative_to(root_resolved):
        raise ValueError("Geçersiz dosya yolu")
    return resolved


# ---------- dosya turu dogrulama ----------

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".webm", ".m4v"}
ALLOWED_EXTENSIONS = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS

_HEIC_BRANDS = {b"heic", b"heix", b"hevc", b"mif1", b"msf1", b"heim", b"heis", b"avic"}


def media_type_for_extension(ext: str) -> str | None:
    ext = ext.lower()
    if ext in IMAGE_EXTENSIONS:
        return "image"
    if ext in VIDEO_EXTENSIONS:
        return "video"
    return None


def sniff_media_type(path: Path) -> tuple[str, str] | None:
    """Ilk 32 bayttan dosya imzasini okur -> (media_type, mime) veya None.

    Sadece MIME header'ina guvenilmedigi icin icerik imzasi da dogrulanir.
    """
    try:
        with open(path, "rb") as f:
            head = f.read(32)
    except OSError:
        return None

    if len(head) < 12:
        return None

    if head.startswith(b"\xff\xd8\xff"):
        return "image", "image/jpeg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image", "image/png"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image", "image/webp"
    if head[:4] == b"\x1a\x45\xdf\xa3":
        return "video", "video/webm"
    if head[4:8] == b"ftyp":
        brand = head[8:12]
        if brand in _HEIC_BRANDS:
            return "image", "image/heic"
        if brand == b"qt  ":
            return "video", "video/quicktime"
        if brand == b"M4V ":
            return "video", "video/x-m4v"
        return "video", "video/mp4"
    return None


# ---------- storage sagligi ----------


@dataclass
class StorageHealth:
    ok: bool
    root_exists: bool
    writable: bool
    marker_present: bool
    require_marker: bool
    total_bytes: int
    free_bytes: int
    message: str


def check_storage(upload_root: Path, require_marker: bool) -> StorageHealth:
    """Upload kokunun sagligini kontrol eder.

    Pi uzerinde REQUIRE_STORAGE_MARKER=true iken marker yoksa USB takilmamis
    demektir; uygulama root filesystem'e yanlislikla yazmayi reddeder.
    """
    root_exists = upload_root.is_dir()
    writable = False
    if root_exists:
        probe = upload_root / ".probe"
        try:
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
            writable = True
        except OSError:
            writable = False

    marker_present = (upload_root / MARKER_NAME).is_file()

    total_bytes = free_bytes = 0
    if root_exists:
        try:
            usage = shutil.disk_usage(upload_root)
            total_bytes, free_bytes = usage.total, usage.free
        except OSError:  # pragma: no cover
            pass

    if not root_exists:
        message = "Depolama klasörü bulunamadı."
        ok = False
    elif not writable:
        message = "Depolama klasörüne yazılamıyor."
        ok = False
    elif require_marker and not marker_present:
        message = "Depolama cihazı bağlı değil."
        ok = False
    else:
        message = ""
        ok = True

    return StorageHealth(
        ok=ok,
        root_exists=root_exists,
        writable=writable,
        marker_present=marker_present,
        require_marker=require_marker,
        total_bytes=total_bytes,
        free_bytes=free_bytes,
        message=message,
    )


def ensure_user_tree(upload_root: Path, folder_name: str) -> dict[str, Path]:
    """Kullanici klasor agacini olusturur: original/, thumbs/, tmp/.

    tmp/ ayni dosya sisteminde bulundugu icin finalize atomik rename ile
    yapilabilir - upload yarida kesilirse orijinal dosya zarar gormez.
    """
    base = safe_join(upload_root, folder_name)
    paths = {
        "base": base,
        "original": base / "original",
        "thumbs": base / "thumbs",
        "tmp": base / "tmp",
    }
    for p in paths.values():
        p.mkdir(parents=True, exist_ok=True)
    return paths


def relative_posix(root: Path, path: Path) -> str:
    """storage_path alani icin kokten goreli posix yolu."""
    return path.resolve().relative_to(root.resolve()).as_posix()


def human_size(num_bytes: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if num_bytes < 1024 or unit == "TB":
            return f"{num_bytes:.1f} {unit}" if unit != "B" else f"{num_bytes} B"
        num_bytes /= 1024
    return f"{num_bytes:.1f} TB"  # pragma: no cover


def free_bytes_for(upload_root: Path) -> int:
    try:
        return shutil.disk_usage(upload_root).free
    except OSError:  # pragma: no cover
        return 0
