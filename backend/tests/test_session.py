from pathlib import Path

from app import db as app_db
from app.models import PublicSession, User

HEADERS = {"x-requested-with": "XMLHttpRequest"}


def _post_session(client, name, if_exists=None):
    payload = {"name": name}
    if if_exists:
        payload["if_exists"] = if_exists
    return client.post("/api/session", json=payload, headers=HEADERS)


def test_config_returns_defaults(client):
    res = client.get("/api/config")
    assert res.status_code == 200
    data = res.json()
    assert data["wedding_title"] == "Elif & Erhan"
    assert data["max_upload_mb"] > 0


def test_health_ok(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["storage_ok"] is True


def test_session_creates_user_and_folder(client):
    res = _post_session(client, "Erhan")
    assert res.status_code == 200
    body = res.json()
    assert body["user"]["display_name"] == "Erhan"
    assert body["existed"] is False

    folder = client.upload_root / "Erhan"
    assert (folder / "original").is_dir()
    assert (folder / "thumbs").is_dir()
    assert "wm_session" in res.cookies


def test_session_turkish_name_ascii_folder(client):
    res = _post_session(client, "Ayşe")
    assert res.status_code == 200
    assert res.json()["user"]["folder_name"] == "Ayse"
    assert res.json()["user"]["display_name"] == "Ayşe"
    assert (client.upload_root / "Ayse" / "original").is_dir()


def test_session_empty_name_rejected(client):
    res = _post_session(client, "   ")
    assert res.status_code == 422


def test_session_name_too_long_rejected(client):
    res = _post_session(client, "a" * 65)
    assert res.status_code == 422


def test_session_missing_header_rejected(client):
    res = client.post("/api/session", json={"name": "Erhan"})
    assert res.status_code == 403


def test_session_existing_name_requires_choice(client):
    _post_session(client, "Erhan")
    res = _post_session(client, "Erhan")
    assert res.status_code == 409
    body = res.json()
    assert body["existed"] is True


def test_session_reuse_same_user(client):
    first = _post_session(client, "Erhan").json()
    res = _post_session(client, "Erhan", if_exists="reuse")
    assert res.status_code == 200
    assert res.json()["user"]["id"] == first["user"]["id"]
    assert res.json()["existed"] is True


def test_session_new_creates_suffixed_folder(client):
    _post_session(client, "Erhan")
    res = _post_session(client, "Erhan", if_exists="new")
    assert res.status_code == 200
    assert res.json()["user"]["folder_name"] == "Erhan-2"
    assert (client.upload_root / "Erhan-2" / "original").is_dir()


def test_session_case_insensitive_match(client):
    _post_session(client, "Erhan")
    res = _post_session(client, "erhan")
    assert res.status_code == 409


def test_me_requires_session(client):
    res = client.get("/api/me")
    assert res.status_code == 401


def test_me_with_session(client):
    _post_session(client, "Erhan")
    res = client.get("/api/me")
    assert res.status_code == 200
    assert res.json()["user"]["display_name"] == "Erhan"


def test_session_persists_in_db(client):
    _post_session(client, "Mehmet")
    with app_db._SessionLocal() as db:
        assert db.query(User).count() == 1
        assert db.query(PublicSession).count() == 1
