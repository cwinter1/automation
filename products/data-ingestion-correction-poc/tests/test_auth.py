from app.auth import hash_password, verify_admin_password, verify_password
from app.models import AdminUser, EndUser


def test_password_hash_roundtrip():
    h = hash_password("s3cret")
    assert verify_password("s3cret", h)
    assert not verify_password("wrong", h)


def test_verify_admin_password_uses_env(monkeypatch):
    monkeypatch.setattr("app.config.settings.ADMIN_PASSWORD", "expected-pw")
    assert verify_admin_password("expected-pw")
    assert not verify_admin_password("nope")


def test_master_admin_login_success_and_failure(client):
    resp_ok = client.post("/login", data={"role": "master_admin", "password": "test-admin-pw"}, follow_redirects=False)
    assert resp_ok.status_code == 303
    assert resp_ok.headers["location"] == "/admin"

    client.post("/logout")
    resp_bad = client.post("/login", data={"role": "master_admin", "password": "nope"}, follow_redirects=False)
    assert resp_bad.status_code == 401


def test_named_admin_login_success_and_failure(client, db_session):
    admin = AdminUser(username="ada", password_hash=hash_password("pw123"))
    db_session.add(admin)
    db_session.commit()

    resp_ok = client.post(
        "/login", data={"role": "admin", "username": "ada", "password": "pw123"}, follow_redirects=False
    )
    assert resp_ok.status_code == 303
    assert resp_ok.headers["location"] == "/admin"

    client.post("/logout")
    resp_bad = client.post(
        "/login", data={"role": "admin", "username": "ada", "password": "wrong"}, follow_redirects=False
    )
    assert resp_bad.status_code == 401


def test_named_admin_has_same_admin_access_as_master(client, db_session):
    admin = AdminUser(username="ada", password_hash=hash_password("pw123"))
    db_session.add(admin)
    db_session.commit()

    client.post("/login", data={"role": "admin", "username": "ada", "password": "pw123"})
    resp = client.get("/admin/datasets")
    assert resp.status_code == 200


def test_only_master_admin_can_manage_admin_accounts(client, db_session):
    admin = AdminUser(username="ada", password_hash=hash_password("pw123"))
    db_session.add(admin)
    db_session.commit()

    client.post("/login", data={"role": "admin", "username": "ada", "password": "pw123"})
    resp = client.get("/admin/admins")
    assert resp.status_code == 403
    resp2 = client.post("/admin/admins", json={"username": "new", "password": "pw"})
    assert resp2.status_code == 403

    client.post("/logout")
    client.post("/login", data={"role": "master_admin", "password": "test-admin-pw"})
    resp3 = client.get("/admin/admins")
    assert resp3.status_code == 200


def test_enduser_login_success_and_failure(client, db_session):
    user = EndUser(username="alice", password_hash=hash_password("pw123"))
    db_session.add(user)
    db_session.commit()

    resp_ok = client.post(
        "/login", data={"role": "enduser", "username": "alice", "password": "pw123"}, follow_redirects=False
    )
    assert resp_ok.status_code == 303
    assert resp_ok.headers["location"] == "/review"

    client.post("/logout")
    resp_bad = client.post(
        "/login", data={"role": "enduser", "username": "alice", "password": "wrong"}, follow_redirects=False
    )
    assert resp_bad.status_code == 401


def test_unauthenticated_page_redirects_to_login(client):
    resp = client.get("/admin", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/login"

    resp2 = client.get("/review", follow_redirects=False)
    assert resp2.status_code == 303


def test_unauthenticated_api_returns_403(client):
    resp = client.get("/admin/datasets")
    assert resp.status_code == 403

    resp2 = client.get("/review/grid")
    assert resp2.status_code == 403


def test_role_isolation(client, db_session):
    user = EndUser(username="alice", password_hash=hash_password("pw123"))
    db_session.add(user)
    db_session.commit()
    client.post("/login", data={"role": "enduser", "username": "alice", "password": "pw123"})

    resp = client.get("/admin/datasets")
    assert resp.status_code == 403

    client.post("/logout")
    client.post("/login", data={"role": "master_admin", "password": "test-admin-pw"})
    resp2 = client.get("/review/grid")
    assert resp2.status_code == 403
