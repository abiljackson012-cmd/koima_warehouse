"""Қолданушыларды басқару (тек admin)."""


def _find(admin, name):
    return next(u for u in admin.get("/api/users").get_json()["users"] if u["username"] == name)


def test_only_admin_can_list_users(admin, manager, user):
    assert admin.get("/api/users").status_code == 200
    assert manager.get("/api/users").status_code == 403
    assert user.get("/api/users").status_code == 403


def test_user_list_has_no_password_data(admin, user):
    for u in admin.get("/api/users").get_json()["users"]:
        assert "password_hash" not in u and "password" not in u


def test_admin_changes_role_and_it_takes_effect_immediately(admin, user):
    uid = _find(admin, "student")["id"]
    assert user.post("/api/products", json={"sku": "Z-1", "name": "x", "price": 1}).status_code == 403
    assert admin.patch(f"/api/users/{uid}", json={"role": "manager"}).status_code == 200
    assert user.post("/api/products", json={"sku": "Z-1", "name": "x", "price": 1}).status_code == 201


def test_invalid_role_rejected(admin, user):
    uid = _find(admin, "student")["id"]
    assert admin.patch(f"/api/users/{uid}", json={"role": "superman"}).status_code == 422


def test_admin_cannot_change_or_delete_self(admin):
    me = admin.get("/api/auth/me").get_json()["user"]["id"]
    assert admin.patch(f"/api/users/{me}", json={"role": "user"}).status_code == 409
    assert admin.delete(f"/api/users/{me}").status_code == 409


def test_admin_deletes_user_and_their_token_stops_working(admin, user):
    uid = _find(admin, "student")["id"]
    assert admin.delete(f"/api/users/{uid}").status_code == 204
    assert user.get("/api/auth/me").status_code == 401
    assert admin.delete(f"/api/users/{uid}").status_code == 404
