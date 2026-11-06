"""Себет және тапсырыс: қалдық, атомарлық шегеру, жеке себет, рұқсаттар."""
from conftest import GOOD


def _product(manager, sku, quantity, price=100):
    r = manager.post("/api/products", json={**GOOD, "sku": sku, "quantity": quantity, "price": price,
                                            "min_quantity": 0})
    assert r.status_code == 201
    return r.get_json()["product"]


def _second_buyer(app):
    c = app.test_client()
    r = c.post("/api/auth/register", json={"username": "buyer2", "email": "b2@example.com", "password": "Secret123"})
    assert r.status_code == 201
    assert c.post("/api/auth/login", json={"username": "buyer2", "password": "Secret123"}).status_code == 200
    return c


def test_add_to_cart_and_totals(manager, user):
    p = _product(manager, "C-1", 10, price=250)
    r = user.post("/api/cart", json={"product_id": p["id"], "quantity": 2})
    assert r.status_code == 201
    cart = r.get_json()["cart"]
    assert cart["count"] == 2 and cart["total"] == 500 and cart["items"][0]["name"] == "Сусын"
    user.post("/api/cart", json={"product_id": p["id"], "quantity": 3})  # бар санға қосылады
    assert user.get("/api/cart").get_json()["cart"]["count"] == 5


def test_cannot_put_more_than_stock_in_cart(manager, user):
    p = _product(manager, "C-2", 3)
    r = user.post("/api/cart", json={"product_id": p["id"], "quantity": 4})
    assert r.status_code == 409 and r.get_json()["error"]["code"] == "not_enough_stock"
    user.post("/api/cart", json={"product_id": p["id"], "quantity": 2})
    assert user.post("/api/cart", json={"product_id": p["id"], "quantity": 2}).status_code == 409


def test_out_of_stock_product_cannot_be_added(manager, user):
    p = _product(manager, "C-3", 0)
    r = user.post("/api/cart", json={"product_id": p["id"]})
    assert r.status_code == 409 and r.get_json()["error"]["code"] == "out_of_stock"


def test_update_and_remove_cart_item(manager, user):
    p = _product(manager, "C-4", 10)
    user.post("/api/cart", json={"product_id": p["id"], "quantity": 2})
    r = user.patch(f"/api/cart/{p['id']}", json={"quantity": 5})
    assert r.status_code == 200 and r.get_json()["cart"]["count"] == 5
    assert user.patch(f"/api/cart/{p['id']}", json={"quantity": 11}).status_code == 409
    assert user.patch(f"/api/cart/{p['id']}", json={"quantity": 0}).get_json()["cart"]["count"] == 0
    user.post("/api/cart", json={"product_id": p["id"], "quantity": 1})
    assert user.delete(f"/api/cart/{p['id']}").status_code == 200
    assert user.delete(f"/api/cart/{p['id']}").status_code == 404


def test_cart_validation_and_missing_product(user):
    assert user.post("/api/cart", json={"product_id": 999}).status_code == 404
    assert user.post("/api/cart", json={"product_id": "x"}).status_code == 422
    assert user.post("/api/cart", json={"product_id": 1, "quantity": 0}).status_code == 422


def test_cart_is_private_per_user(manager, app, user):
    p = _product(manager, "C-5", 10)
    user.post("/api/cart", json={"product_id": p["id"], "quantity": 1})
    other = _second_buyer(app)
    assert other.get("/api/cart").get_json()["cart"]["count"] == 0


def test_checkout_decreases_stock_and_logs_movement(manager, user):
    p = _product(manager, "C-6", 10, price=300)
    user.post("/api/cart", json={"product_id": p["id"], "quantity": 4})
    r = user.post("/api/orders")
    assert r.status_code == 201
    order = r.get_json()["order"]
    assert order["total"] == 1200 and order["status"] == "new" and order["items"][0]["quantity"] == 4
    assert manager.get(f"/api/products/{p['id']}").get_json()["product"]["quantity"] == 6
    assert user.get("/api/cart").get_json()["cart"]["count"] == 0
    move = manager.get("/api/movements").get_json()["movements"][0]
    assert move["type"] == "out" and move["username"] == "student" and move["quantity"] == 4


def test_empty_cart_checkout_rejected(user):
    r = user.post("/api/orders")
    assert r.status_code == 422 and r.get_json()["error"]["code"] == "cart_empty"


def test_stock_changed_after_cart_rolls_back_whole_order(manager, user):
    a = _product(manager, "C-7", 10)
    b = _product(manager, "C-8", 5)
    user.post("/api/cart", json={"product_id": a["id"], "quantity": 4})
    user.post("/api/cart", json={"product_id": b["id"], "quantity": 3})
    # Себетке салғаннан кейін қоймадан біреу шығарып жіберді
    manager.post(f"/api/products/{b['id']}/movements", json={"type": "out", "quantity": 3})
    r = user.post("/api/orders")
    assert r.status_code == 409 and r.get_json()["error"]["code"] == "not_enough_stock"
    # Алдымен азайған A тауары қайтарылуы керек (толық атомарлық)
    assert manager.get(f"/api/products/{a['id']}").get_json()["product"]["quantity"] == 10
    assert manager.get("/api/orders").get_json()["orders"] == []
    assert user.get("/api/cart").get_json()["cart"]["count"] == 7


def test_orders_visibility_and_status(manager, app, user):
    p = _product(manager, "C-9", 10)
    user.post("/api/cart", json={"product_id": p["id"], "quantity": 1})
    oid = user.post("/api/orders").get_json()["order"]["id"]
    other = _second_buyer(app)
    assert [o["id"] for o in user.get("/api/orders").get_json()["orders"]] == [oid]
    assert other.get("/api/orders").get_json()["orders"] == []
    assert manager.get("/api/orders").get_json()["orders"][0]["id"] == oid
    assert user.patch(f"/api/orders/{oid}", json={"status": "done"}).status_code == 403
    r = manager.patch(f"/api/orders/{oid}", json={"status": "done"})
    assert r.status_code == 200 and r.get_json()["order"]["status"] == "done"
    assert manager.patch(f"/api/orders/{oid}", json={"status": "cancelled"}).status_code == 422
    assert manager.patch("/api/orders/999", json={"status": "done"}).status_code == 404


def test_cart_and_orders_require_login(anon):
    assert anon.get("/api/cart").status_code == 401
    assert anon.post("/api/orders").status_code == 401
