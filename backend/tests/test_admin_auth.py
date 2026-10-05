"""Admin auth testleri - login, brute force, CSRF, cookie guvenligi."""

from tests.conftest import ADMIN_PASS, ADMIN_USER

HEADERS = {"x-requested-with": "XMLHttpRequest"}


def _login(client, username=ADMIN_USER, password=ADMIN_PASS):
    return client.post(
        "/api/admin/login",
        json={"username": username, "password": password},
        headers=HEADERS,
    )


def _login_ok(client):
    res = _login(client)
    assert res.status_code == 200
    csrf = res.json()["csrf_token"]
    return {"x-requested-with": "XMLHttpRequest", "x-csrf-token": csrf}


def test_login_success_sets_cookie(client):
    res = _login(client)
    assert res.status_code == 200
    assert res.json()["username"] == ADMIN_USER
    assert "csrf_token" in res.json()
    set_cookie = res.headers["set-cookie"]
    assert "wm_admin=" in set_cookie
    assert "httponly" in set_cookie.lower()
    assert "samesite=strict" in set_cookie.lower()


def test_login_wrong_password(client):
    res = _login(client, password="yanlis-sifre")
    assert res.status_code == 401
    assert "Kullanıcı adı veya şifre hatalı" in res.json()["detail"]


def test_login_wrong_username(client):
    res = _login(client, username="baskasi")
    assert res.status_code == 401


def test_login_missing_header_rejected(client):
    res = client.post(
        "/api/admin/login",
        json={"username": ADMIN_USER, "password": ADMIN_PASS},
    )
    assert res.status_code == 403


def test_login_brute_force_lockout(client):
    for _ in range(5):
        res = _login(client, password="yanlis")
        assert res.status_code == 401
    # 6. deneme - dogru sifre olsa bile engellenmeli
    res = _login(client)
    assert res.status_code == 429


def test_login_lockout_clears_on_success_before_limit(client):
    for _ in range(4):
        _login(client, password="yanlis")
    res = _login(client)  # 5. hakta dogru giris
    assert res.status_code == 200
    res = _login(client)
    assert res.status_code == 200, "basarili giristen sonra sayaç sıfırlanmalı"


def test_login_without_configured_hash(client_factory):
    client = client_factory(ADMIN_PASSWORD_HASH="")
    res = _login(client)
    assert res.status_code == 503


def test_me_requires_session(client):
    res = client.get("/api/admin/me")
    assert res.status_code == 401


def test_me_with_session(client):
    _login_ok(client)
    res = client.get("/api/admin/me")
    assert res.status_code == 200
    assert res.json()["username"] == ADMIN_USER


def test_logout_invalidates_session(client):
    headers = _login_ok(client)
    res = client.post("/api/admin/logout", headers=headers)
    assert res.status_code == 200
    res = client.get("/api/admin/me")
    assert res.status_code == 401


def test_logout_requires_csrf(client):
    _login(client)
    res = client.post("/api/admin/logout", headers=HEADERS)
    assert res.status_code == 403


def test_mutation_requires_csrf(client):
    _login(client)  # cookie set, csrf bilinmiyor
    res = client.post("/api/admin/logout", headers=HEADERS)
    assert res.status_code == 403
