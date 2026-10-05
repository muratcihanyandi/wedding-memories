"""Admin veri API testleri - stats, users, dosya islemleri, ZIP, QR, settings."""

import io
import zipfile

from PIL import Image

from tests.conftest import ADMIN_PASS, ADMIN_USER

HEADERS = {"x-requested-with": "XMLHttpRequest"}


def _png_bytes(color=(246, 231, 228)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (64, 48), color).save(buf, format="PNG")
    return buf.getvalue()


MP4_BYTES = b"\x00\x00\x00\x18ftypisom\x00\x00\x02\x00isomiso2avc1mp41" + b"\x00" * 64


def _admin_login(client):
    res = client.post(
        "/api/admin/login",
        json={"username": ADMIN_USER, "password": ADMIN_PASS},
        headers=HEADERS,
    )
    assert res.status_code == 200
    return {"x-requested-with": "XMLHttpRequest", "x-csrf-token": res.json()["csrf_token"]}


def _create_user_with_uploads(client, name, files):
    res = client.post("/api/session", json={"name": name}, headers=HEADERS)
    assert res.status_code == 200
    user = res.json()["user"]
    for filename, data, ctype in files:
        res = client.post(
            "/api/uploads",
            files={"files": (filename, data, ctype)},
            headers=HEADERS,
        )
        assert res.status_code == 200, res.text
    return user


def _seed(client):
    """2 kullanici, 3 foto, 1 video olusturur; admin header'lari doner."""
    admin_headers = _admin_login(client)
    erhan = _create_user_with_uploads(client, "Erhan", [
        ("IMG_1.jpg", _png_bytes(), "image/png"),
        ("IMG_2.jpg", _png_bytes((255, 255, 255)), "image/png"),
    ])
    ayse = _create_user_with_uploads(client, "Ayse", [
        ("foto.png", _png_bytes((200, 220, 240)), "image/png"),
        ("video.mp4", MP4_BYTES, "video/mp4"),
    ])
    return admin_headers, erhan, ayse


def test_stats(client):
    admin_headers, erhan, ayse = _seed(client)
    res = client.get("/api/admin/stats", headers=admin_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["users"] == 2
    assert data["photos"] == 3
    assert data["videos"] == 1
    assert data["files"] == 4
    assert data["total_size"] > 0
    assert data["storage"]["total_bytes"] > 0
    assert data["storage"]["ok"] is True


def test_stats_requires_admin(client):
    res = client.get("/api/admin/stats")
    assert res.status_code == 401


def test_users_list(client):
    admin_headers, erhan, ayse = _seed(client)
    res = client.get("/api/admin/users", headers=admin_headers)
    assert res.status_code == 200
    users = res.json()["users"]
    assert len(users) == 2
    by_name = {u["folder_name"]: u for u in users}
    assert by_name["Erhan"]["file_count"] == 2
    assert by_name["Ayse"]["file_count"] == 2

    # liste boyutlari kullanici detayindaki dosya boyutlariyla ortusmeli
    for folder, user in by_name.items():
        detail = client.get(f"/api/admin/users/{user['id']}", headers=admin_headers).json()
        assert user["total_size"] == sum(f["size"] for f in detail["files"])


def test_user_detail(client):
    admin_headers, erhan, _ = _seed(client)
    res = client.get(f"/api/admin/users/{erhan['id']}", headers=admin_headers)
    assert res.status_code == 200
    detail = res.json()
    assert detail["display_name"] == "Erhan"
    assert len(detail["files"]) == 2
    assert all(f["exists_on_disk"] for f in detail["files"])


def test_user_detail_missing_file_no_error(client):
    admin_headers, erhan, _ = _seed(client)
    # dosyayi diskten manuel sil - panel hata vermemeli (spec #22)
    for f in (client.upload_root / "Erhan" / "original").iterdir():
        f.unlink()
    res = client.get(f"/api/admin/users/{erhan['id']}", headers=admin_headers)
    assert res.status_code == 200
    assert all(not f["exists_on_disk"] for f in res.json()["files"])


def test_user_404(client):
    admin_headers = _admin_login(client)
    res = client.get("/api/admin/users/9999", headers=admin_headers)
    assert res.status_code == 404


def test_delete_file(client):
    admin_headers, erhan, _ = _seed(client)
    res = client.get(f"/api/admin/users/{erhan['id']}", headers=admin_headers)
    file_id = res.json()["files"][0]["id"]
    res = client.delete(f"/api/admin/files/{file_id}", headers=admin_headers)
    assert res.status_code == 200
    original_dir = client.upload_root / "Erhan" / "original"
    assert len(list(original_dir.iterdir())) == 1
    res = client.get(f"/api/admin/users/{erhan['id']}", headers=admin_headers)
    assert len(res.json()["files"]) == 1


def test_delete_requires_csrf(client):
    admin_headers, erhan, _ = _seed(client)
    res = client.get(f"/api/admin/users/{erhan['id']}", headers=admin_headers)
    file_id = res.json()["files"][0]["id"]
    res = client.delete(f"/api/admin/files/{file_id}", headers=HEADERS)
    assert res.status_code == 403


def test_delete_batch(client):
    admin_headers, erhan, _ = _seed(client)
    res = client.get(f"/api/admin/users/{erhan['id']}", headers=admin_headers)
    ids = [f["id"] for f in res.json()["files"]]
    res = client.post("/api/admin/files/delete-batch", json={"ids": ids}, headers=admin_headers)
    assert res.status_code == 200
    assert res.json()["deleted"] == 2
    assert not any((client.upload_root / "Erhan" / "original").iterdir())


def test_delete_user_removes_folder_and_records(client):
    admin_headers, erhan, _ = _seed(client)
    res = client.delete(f"/api/admin/users/{erhan['id']}", headers=admin_headers)
    assert res.status_code == 200
    assert not (client.upload_root / "Erhan").exists()
    res = client.get("/api/admin/users", headers=admin_headers)
    assert all(u["folder_name"] != "Erhan" for u in res.json()["users"])
    res = client.get(f"/api/admin/users/{erhan['id']}", headers=admin_headers)
    assert res.status_code == 404


def test_download_file(client):
    admin_headers, _, ayse = _seed(client)
    res = client.get(f"/api/admin/users/{ayse['id']}", headers=admin_headers)
    video = next(f for f in res.json()["files"] if f["media_type"] == "video")
    res = client.get(f"/api/admin/files/{video['id']}/download", headers=admin_headers)
    assert res.status_code == 200
    assert res.content == MP4_BYTES
    assert "attachment" in res.headers.get("content-disposition", "")


def test_download_file_range_support(client):
    admin_headers, _, ayse = _seed(client)
    res = client.get(f"/api/admin/users/{ayse['id']}", headers=admin_headers)
    video = next(f for f in res.json()["files"] if f["media_type"] == "video")
    res = client.get(
        f"/api/admin/files/{video['id']}/download",
        headers={**admin_headers, "Range": "bytes=0-9"},
    )
    assert res.status_code in (200, 206)
    if res.status_code == 206:
        assert res.content == MP4_BYTES[:10]


def test_thumb_served(client):
    admin_headers, erhan, _ = _seed(client)
    res = client.get(f"/api/admin/users/{erhan['id']}", headers=admin_headers)
    photo = res.json()["files"][0]
    res = client.get(f"/api/admin/thumbs/{photo['id']}", headers=admin_headers)
    assert res.status_code == 200
    assert res.headers["content-type"] == "image/webp"


def test_thumb_video_404(client):
    admin_headers, _, ayse = _seed(client)
    res = client.get(f"/api/admin/users/{ayse['id']}", headers=admin_headers)
    video = next(f for f in res.json()["files"] if f["media_type"] == "video")
    res = client.get(f"/api/admin/thumbs/{video['id']}", headers=admin_headers)
    assert res.status_code == 404


def test_zip_download_valid_archive(client):
    admin_headers, erhan, _ = _seed(client)
    res = client.get(f"/api/admin/users/{erhan['id']}/zip", headers=admin_headers)
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/zip"

    archive = zipfile.ZipFile(io.BytesIO(res.content))
    names = archive.namelist()
    assert sorted(names) == ["IMG_1.jpg", "IMG_2.jpg"]
    assert archive.read("IMG_1.jpg") == _png_bytes()
    assert archive.testzip() is None, "CRC hatali olmamali"


def test_zip_skips_missing_files(client):
    admin_headers, erhan, _ = _seed(client)
    files = list((client.upload_root / "Erhan" / "original").iterdir())
    files[0].unlink()
    res = client.get(f"/api/admin/users/{erhan['id']}/zip", headers=admin_headers)
    assert res.status_code == 200
    archive = zipfile.ZipFile(io.BytesIO(res.content))
    assert len(archive.namelist()) == 1


def test_zip_empty_user_404(client):
    admin_headers = _admin_login(client)
    res = client.post("/api/session", json={"name": "Bos"}, headers=HEADERS)
    user_id = res.json()["user"]["id"]
    res = client.get(f"/api/admin/users/{user_id}/zip", headers=admin_headers)
    assert res.status_code == 404


def test_qr_png(client):
    admin_headers = _admin_login(client)
    res = client.get("/api/admin/qr.png?size=512", headers=admin_headers)
    assert res.status_code == 200
    assert res.headers["content-type"] == "image/png"
    assert res.content.startswith(b"\x89PNG")


def test_settings_read_update(client):
    admin_headers = _admin_login(client)
    res = client.get("/api/admin/settings", headers=admin_headers)
    assert res.status_code == 200
    assert res.json()["wedding_title"] == "Elif & Erhan"

    res = client.put(
        "/api/admin/settings",
        json={"wedding_title": "Zeynep & Ali", "public_url": "http://192.168.1.50"},
        headers=admin_headers,
    )
    assert res.status_code == 200

    res = client.get("/api/config")
    assert res.json()["wedding_title"] == "Zeynep & Ali"


def test_settings_invalid_url_rejected(client):
    admin_headers = _admin_login(client)
    res = client.put(
        "/api/admin/settings",
        json={"public_url": "javascript:alert(1)"},
        headers=admin_headers,
    )
    assert res.status_code == 422


def test_cleanup_removes_orphan_records(client):
    admin_headers, erhan, _ = _seed(client)
    files = list((client.upload_root / "Erhan" / "original").iterdir())
    files[0].unlink()

    res = client.post("/api/admin/cleanup", headers=admin_headers)
    assert res.status_code == 200
    assert res.json()["removed_records"] == 1

    res = client.get(f"/api/admin/users/{erhan['id']}", headers=admin_headers)
    assert len(res.json()["files"]) == 1


def test_cleanup_reports_orphan_disk_files(client):
    admin_headers, erhan, _ = _seed(client)
    orphan = client.upload_root / "Erhan" / "original" / "yetim.jpg"
    orphan.write_bytes(b"\xff\xd8\xff\xe0xx")

    res = client.post("/api/admin/cleanup", headers=admin_headers)
    assert res.status_code == 200
    assert res.json()["orphan_files"] == 1
    assert orphan.is_file(), "orphan dosya silinmemeli - sadece raporlanmali"


def test_backup_sqlite(client):
    admin_headers = _admin_login(client)
    _seed(client)
    res = client.get("/api/admin/backup.sqlite", headers=admin_headers)
    assert res.status_code == 200
    assert res.content.startswith(b"SQLite format 3")
