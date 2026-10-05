"""Storage guvenlik katmani testleri - path traversal, sanitize, magic bytes."""

from pathlib import Path

import pytest

from app.storage import (
    MARKER_NAME,
    check_storage,
    sanitize_display_name,
    sanitize_filename,
    safe_join,
    sniff_media_type,
    unique_filename,
    unique_folder_name,
)


# ---------- sanitize_display_name ----------

@pytest.mark.parametrize("raw,expected", [
    ("Erhan", "Erhan"),
    ("  Erhan  ", "Erhan"),
    ("Ayse", "Ayse"),
    ("Ayşe", "Ayse"),
    ("Ümit Şahin", "Umit Sahin"),
    ("İbrahim Çağlar", "Ibrahim Caglar"),
    ("Ömer Faruk", "Omer Faruk"),
    ("ayaş    kalesi", "ayas kalesi"),
    ("a/b", "a b"),
])
def test_display_name_transliteration(raw, expected):
    assert sanitize_display_name(raw) == expected


@pytest.mark.parametrize("raw", [
    "",
    "   ",
    "!!!???***",
    "..",
    "///",
])
def test_display_name_invalid_falls_back(raw):
    assert sanitize_display_name(raw) == "Misafir"


def test_display_name_neutralizes_traversal():
    result = sanitize_display_name("../../malicious")
    assert result not in ("", "..")
    assert "/" not in result and "\\" not in result and "." not in result


def test_display_name_length_limit():
    long_name = "a" * 100
    result = sanitize_display_name(long_name)
    assert len(result) <= 40
    assert result == "a" * 40


def test_display_name_strips_dangerous_chars():
    result = sanitize_display_name("Er<script>han\x00")
    assert "<" not in result and ">" not in result and "\x00" not in result


# ---------- unique_folder_name ----------

def test_unique_folder_name_no_collision():
    assert unique_folder_name("Erhan", set()) == "Erhan"


def test_unique_folder_name_collisions():
    existing = {"Erhan", "Erhan-2"}
    assert unique_folder_name("Erhan", existing) == "Erhan-3"


# ---------- sanitize_filename ----------

def test_filename_strips_path_components():
    assert sanitize_filename("..\\..\\evil.php") == "evil.php"
    assert sanitize_filename("../../evil.jpg") == "evil.jpg"
    assert sanitize_filename("/etc/passwd.jpg") == "passwd.jpg"


def test_filename_transliterates_and_replaces():
    assert sanitize_filename("fotoğrafım.jpg") == "fotografim.jpg"
    assert sanitize_filename("my file:name*.jpg") == "my file_name_.jpg"


def test_filename_hidden_file_prefix():
    result = sanitize_filename(".profile.jpg")
    assert not result.startswith(".")


def test_filename_length_limit_keeps_extension():
    raw = "a" * 200 + ".jpg"
    result = sanitize_filename(raw)
    assert len(result) <= 100
    assert result.endswith(".jpg")


def test_filename_empty_fallback():
    assert sanitize_filename("???") != ""


def test_unique_filename():
    assert unique_filename("IMG_1234.jpg", set()) == "IMG_1234.jpg"
    assert unique_filename("IMG_1234.jpg", {"IMG_1234.jpg"}) == "IMG_1234_2.jpg"
    assert unique_filename("IMG_1234.jpg", {"IMG_1234.jpg", "IMG_1234_2.jpg"}) == "IMG_1234_3.jpg"


# ---------- safe_join ----------

def test_safe_join_inside_root(tmp_path):
    result = safe_join(tmp_path, "Erhan", "original", "foto.jpg")
    assert str(result).startswith(str(tmp_path))


def test_safe_join_blocks_traversal(tmp_path):
    with pytest.raises(ValueError):
        safe_join(tmp_path, "Erhan", "..", "..", "etc", "passwd")


def test_safe_join_blocks_absolute_escape(tmp_path):
    with pytest.raises(ValueError):
        safe_join(tmp_path, "Erhan", "/etc/passwd")


# ---------- magic bytes ----------

PNG_BYTES = bytes.fromhex("89504e470d0a1a0a0000000d49484452") + b"\x00" * 16


def _write(tmp_path, name, data):
    p = tmp_path / name
    p.write_bytes(data)
    return p


def test_sniff_png(tmp_path):
    media, mime = sniff_media_type(_write(tmp_path, "a.png", PNG_BYTES))
    assert media == "image" and mime == "image/png"


def test_sniff_jpeg(tmp_path):
    media, mime = sniff_media_type(_write(tmp_path, "a.jpg", b"\xff\xd8\xff\xe0" + b"\x00" * 8))
    assert media == "image" and mime == "image/jpeg"


def test_sniff_webp(tmp_path):
    media, mime = sniff_media_type(_write(tmp_path, "a.webp", b"RIFF\x24\x00\x00\x00WEBPVP8 "))
    assert media == "image" and mime == "image/webp"


def test_sniff_heic(tmp_path):
    media, mime = sniff_media_type(_write(tmp_path, "a.heic", b"\x00\x00\x00\x18ftypheic" + b"\x00" * 8))
    assert media == "image" and mime == "image/heic"


def test_sniff_mp4(tmp_path):
    media, mime = sniff_media_type(_write(tmp_path, "a.mp4", b"\x00\x00\x00\x18ftypisom" + b"\x00" * 8))
    assert media == "video" and mime == "video/mp4"


def test_sniff_mov(tmp_path):
    media, mime = sniff_media_type(_write(tmp_path, "a.mov", b"\x00\x00\x00\x18ftypqt  " + b"\x00" * 8))
    assert media == "video" and mime == "video/quicktime"


def test_sniff_webm(tmp_path):
    media, mime = sniff_media_type(_write(tmp_path, "a.webm", b"\x1a\x45\xdf\xa3" + b"\x00" * 8))
    assert media == "video" and mime == "video/webm"


def test_sniff_rejects_unknown(tmp_path):
    assert sniff_media_type(_write(tmp_path, "a.exe", b"MZ\x90\x00" + b"\x00" * 8)) is None
    assert sniff_media_type(_write(tmp_path, "a.php", b"<?php echo 1; ?>")) is None
    assert sniff_media_type(_write(tmp_path, "a.zip", b"PK\x03\x04" + b"\x00" * 8)) is None
    assert sniff_media_type(_write(tmp_path, "a.txt", b"merhaba dunya")) is None


# ---------- storage health ----------

def test_storage_health_with_marker(tmp_path):
    (tmp_path / MARKER_NAME).write_text("ok", encoding="utf-8")
    health = check_storage(tmp_path, require_marker=True)
    assert health.ok is True


def test_storage_health_marker_missing_required(tmp_path):
    health = check_storage(tmp_path, require_marker=True)
    assert health.ok is False


def test_storage_health_marker_missing_but_not_required(tmp_path):
    health = check_storage(tmp_path, require_marker=False)
    assert health.ok is True


def test_storage_health_missing_root(tmp_path):
    health = check_storage(tmp_path / "yok", require_marker=False)
    assert health.ok is False
