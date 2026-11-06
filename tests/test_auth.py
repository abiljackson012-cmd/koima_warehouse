"""Авторизация: тіркелу, кіру, шығу, валидация, токен қауіпсіздігі."""
import jwt

REG = {"username": "aidar", "email": "Aidar@Example.com", "password": "Secret123"}


def test_register_success_defaults_to_buyer_role(anon):
    r = anon.post("/api/auth/register", json=REG)
    assert r.status_code == 201
    u = r.get_json()["user"]
    assert u["role"] == "buyer" and u["email"] == "aidar@example.com"
    assert "password" not in u and "password_hash" not in u


def test_register_cannot_choose_role(anon):
    r = anon.post("/api/auth/register", json={**REG, "role": "admin"})
    assert r.status_code == 422
    assert any(d["field"] == "role" for d in r.get_json()["error"]["details"])


def test_register_validation_errors(anon):
    r = anon.post("/api/auth/register", json={"username": "a!", "email": "bad", "password": "123"})
    assert r.status_code == 422
    fields = {d["field"] for d in r.get_json()["error"]["details"]}
    assert {"username", "email", "password"} <= fields


def test_password_needs_letter_and_digit(anon):
    r = anon.post("/api/auth/register", json={**REG, "password": "onlyletters"})
    assert r.status_code == 422


def test_register_duplicate_username_and_email(anon):
    assert anon.post("/api/auth/register", json=REG).status_code == 201
    r = anon.post("/api/auth/register", json={**REG, "username": "AIDAR", "email": "other@example.com"})
    assert r.status_code == 409 and r.get_json()["error"]["code"] == "username_taken"
    r = anon.post("/api/auth/register", json={**REG, "username": "other"})
    assert r.status_code == 409 and r.get_json()["error"]["code"] == "email_taken"


def test_invalid_json_body(anon):
    r = anon.post("/api/auth/register", data="not json", content_type="application/json")
    assert r.status_code == 400 and r.get_json()["error"]["code"] == "invalid_json"


def test_login_me_logout_flow(anon):
    anon.post("/api/auth/register", json=REG)
    r = anon.post("/api/auth/login", json={"username": "aidar", "password": "Secret123"})
    assert r.status_code == 200
    assert "HttpOnly" in r.headers["Set-Cookie"]
    assert anon.get("/api/auth/me").get_json()["user"]["username"] == "aidar"
    assert anon.post("/api/auth/logout").status_code == 200
    assert anon.get("/api/auth/me").status_code == 401


def test_logout_revokes_token_even_if_reused(app, anon):
    anon.post("/api/auth/register", json=REG)
    token = anon.post("/api/auth/login", json={"username": "aidar", "password": "Secret123"}) \
        .headers["Set-Cookie"].split("token=")[1].split(";")[0]
    anon.post("/api/auth/logout")
    r = app.test_client().get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401 and r.get_json()["error"]["code"] == "token_revoked"


def test_login_by_email_works(anon):
    anon.post("/api/auth/register", json=REG)
    r = anon.post("/api/auth/login", json={"username": "aidar@example.com", "password": "Secret123"})
    assert r.status_code == 200


def test_wrong_password_and_unknown_user_same_message(anon):
    anon.post("/api/auth/register", json=REG)
    a = anon.post("/api/auth/login", json={"username": "aidar", "password": "Wrong123"})
    b = anon.post("/api/auth/login", json={"username": "nobody", "password": "Wrong123"})
    assert a.status_code == b.status_code == 401
    assert a.get_json() == b.get_json()


def test_login_rate_limit(anon):
    for _ in range(5):
        anon.post("/api/auth/login", json={"username": "x", "password": "y"})
    r = anon.post("/api/auth/login", json={"username": "x", "password": "y"})
    assert r.status_code == 429


def test_protected_route_without_token(anon):
    assert anon.get("/api/products").status_code == 401


def test_tampered_token_rejected(app, anon):
    bad = jwt.encode({"sub": "1", "jti": "x", "exp": 9999999999}, "another-secret-key-0123456789-abcdef", algorithm="HS256")
    r = anon.get("/api/auth/me", headers={"Authorization": f"Bearer {bad}"})
    assert r.status_code == 401 and r.get_json()["error"]["code"] == "invalid_token"


def test_expired_token_rejected(app, anon):
    old = jwt.encode({"sub": "1", "jti": "x", "exp": 1}, app.config["SECRET_KEY"], algorithm="HS256")
    r = anon.get("/api/auth/me", headers={"Authorization": f"Bearer {old}"})
    assert r.status_code == 401 and r.get_json()["error"]["code"] == "token_expired"


def test_seeded_admin_and_manager_roles(admin, manager):
    assert admin.get("/api/auth/me").get_json()["user"]["role"] == "admin"
    assert manager.get("/api/auth/me").get_json()["user"]["role"] == "manager"
