"""Тауарлар CRUD, рөлдер, кіріс/шығыс бизнес-логикасы, валидация."""
from conftest import GOOD


def test_user_can_read_but_not_write(user, product):
    assert user.get("/api/products").status_code == 200
    assert user.get(f"/api/products/{product['id']}").status_code == 200
    assert user.post("/api/products", json=GOOD).status_code == 403
    assert user.patch(f"/api/products/{product['id']}", json={"name": "X"}).status_code == 403
    assert user.post(f"/api/products/{product['id']}/movements", json={"type": "in", "quantity": 1}).status_code == 403
    assert user.delete(f"/api/products/{product['id']}").status_code == 403


def test_manager_creates_and_logs_initial_stock(manager, product):
    assert product["quantity"] == 10 and product["low"] is False
    moves = manager.get("/api/movements").get_json()["movements"]
    assert moves[0]["type"] == "init" and moves[0]["quantity"] == 10 and moves[0]["username"] == "manager_test"


def test_manager_cannot_delete_admin_can(manager, admin, product):
    assert manager.delete(f"/api/products/{product['id']}").status_code == 403
    assert admin.delete(f"/api/products/{product['id']}").status_code == 204
    assert admin.get(f"/api/products/{product['id']}").status_code == 404


def test_history_survives_product_delete(admin, product):
    admin.delete(f"/api/products/{product['id']}")
    moves = admin.get("/api/movements").get_json()["movements"]
    assert moves and moves[0]["product_name"] == "Сусын"


def test_create_validation(manager):
    bad = {"sku": "!", "name": "", "price": -5, "min_quantity": "many"}
    r = manager.post("/api/products", json=bad)
    assert r.status_code == 422
    fields = {d["field"] for d in r.get_json()["error"]["details"]}
    assert {"sku", "name", "price", "min_quantity"} <= fields


def test_price_must_be_integer_not_string_or_bool(manager):
    assert manager.post("/api/products", json={**GOOD, "price": "500"}).status_code == 422
    assert manager.post("/api/products", json={**GOOD, "price": True}).status_code == 422


def test_duplicate_sku_conflict(manager, product):
    r = manager.post("/api/products", json=GOOD)
    assert r.status_code == 409 and r.get_json()["error"]["code"] == "sku_taken"


def test_patch_and_put(manager, product):
    pid = product["id"]
    r = manager.patch(f"/api/products/{pid}", json={"price": 700})
    assert r.status_code == 200 and r.get_json()["product"]["price"] == 700
    assert manager.patch(f"/api/products/{pid}", json={}).status_code == 422
    full = {"sku": "TS-1", "name": "Жаңа", "category": "Басқа", "price": 1, "min_quantity": 0}
    assert manager.put(f"/api/products/{pid}", json=full).get_json()["product"]["name"] == "Жаңа"
    assert manager.put(f"/api/products/{pid}", json={"name": "only"}).status_code == 422


def test_quantity_cannot_be_edited_directly(manager, product):
    r = manager.patch(f"/api/products/{product['id']}", json={"quantity": 999})
    assert r.status_code == 422


def test_patch_sku_conflict_with_other_product(manager, product):
    manager.post("/api/products", json={**GOOD, "sku": "TS-2"})
    assert manager.patch(f"/api/products/{product['id']}", json={"sku": "TS-2"}).status_code == 409
    assert manager.patch(f"/api/products/{product['id']}", json={"sku": "TS-1"}).status_code == 200


def test_not_found(manager):
    assert manager.get("/api/products/9999").status_code == 404
    assert manager.patch("/api/products/9999", json={"name": "x"}).status_code == 404
    assert manager.post("/api/products/9999/movements", json={"type": "in", "quantity": 1}).status_code == 404


def test_stock_in_and_out(manager, product):
    pid = product["id"]
    r = manager.post(f"/api/products/{pid}/movements", json={"type": "in", "quantity": 5})
    assert r.status_code == 201 and r.get_json()["product"]["quantity"] == 15
    r = manager.post(f"/api/products/{pid}/movements", json={"type": "out", "quantity": 12})
    assert r.get_json()["product"]["quantity"] == 3 and r.get_json()["product"]["low"] is True


def test_cannot_ship_more_than_in_stock(manager, product):
    pid = product["id"]
    r = manager.post(f"/api/products/{pid}/movements", json={"type": "out", "quantity": 11})
    assert r.status_code == 409 and r.get_json()["error"]["code"] == "not_enough_stock"
    assert manager.get(f"/api/products/{pid}").get_json()["product"]["quantity"] == 10
    types = [m["type"] for m in manager.get("/api/movements").get_json()["movements"]]
    assert types == ["init"]  # сәтсіз шығыс тарихқа түспеген


def test_movement_validation(manager, product):
    url = f"/api/products/{product['id']}/movements"
    assert manager.post(url, json={"type": "steal", "quantity": 1}).status_code == 422
    assert manager.post(url, json={"type": "in", "quantity": 0}).status_code == 422
    assert manager.post(url, json={"type": "in", "quantity": -3}).status_code == 422
    assert manager.post(url, json={"type": "in", "quantity": 1.5}).status_code == 422


def test_search_low_filter_and_pagination(manager):
    manager.post("/api/products", json={**GOOD, "sku": "A-1", "name": "Күріш", "quantity": 1, "min_quantity": 5})
    manager.post("/api/products", json={**GOOD, "sku": "B-1", "name": "Макарон", "quantity": 50, "min_quantity": 5})
    assert len(manager.get("/api/products?search=күріш").get_json()["products"]) == 1  # кіші әріппен де табады
    assert len(manager.get("/api/products?search=КҮРІШ").get_json()["products"]) == 1
    low = manager.get("/api/products?low=1").get_json()["products"]
    assert [p["sku"] for p in low] == ["A-1"]
    page = manager.get("/api/products?limit=1&offset=1").get_json()
    assert page["total"] == 2 and len(page["products"]) == 1
    assert manager.get("/api/products?limit=0").status_code == 422
    assert manager.get("/api/products?low=maybe").status_code == 422


def test_stats(manager):
    manager.post("/api/products", json={**GOOD, "sku": "A-1", "price": 100, "quantity": 2, "min_quantity": 5})
    manager.post("/api/products", json={**GOOD, "sku": "B-1", "price": 10, "quantity": 30, "min_quantity": 5})
    s = manager.get("/api/stats").get_json()["stats"]
    assert s == {"products": 2, "total_quantity": 32, "total_value": 500, "low_stock": 1}


def test_unknown_route_and_method_return_json(manager):
    r = manager.get("/api/nothing")
    assert r.status_code == 404 and r.get_json()["error"]["code"] == "not_found"
    assert manager.delete("/api/stats").status_code == 405
