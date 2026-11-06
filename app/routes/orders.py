import logging

from flask import Blueprint, g, jsonify

from ..auth import require
from ..db import get_db, now
from ..errors import AppError
from ..validation import OrderStatusIn, parse
from . import json_body
from .products import _log_move

log = logging.getLogger("warehouse")
bp = Blueprint("orders", __name__, url_prefix="/api/orders")
STAFF = ("manager", "admin")
ORDER_COLS = "id, username, total, status, created_at"


def _with_items(db, orders):
    for o in orders:
        o["items"] = db.query(
            "SELECT product_name, price, quantity FROM order_items WHERE order_id = ? ORDER BY id", (o["id"],))
    return orders


def _one(db, oid):
    order = db.one(f"SELECT {ORDER_COLS} FROM orders WHERE id = ?", (oid,))
    if not order:
        raise AppError(404, "order_not_found", "Тапсырыс табылмады.")
    return _with_items(db, [order])[0]


@bp.post("")
@require()
def checkout():
    db = get_db()
    items = db.query(
        "SELECT c.product_id, c.quantity, p.name, p.price FROM cart_items c "
        "JOIN products p ON p.id = c.product_id WHERE c.user_id = ? ORDER BY c.id", (g.user["id"],))
    if not items:
        raise AppError(422, "cart_empty", "Себет бос. Алдымен тауар қосыңыз.")
    total = 0
    for it in items:
        # Қалдық жеткілікті болғанда ғана азаяды. Бір тауар жетпесе, қате жауабы қайтады,
        # ал after_request бұрын азайған барлық жазбаны қайтарады (толық атомарлық).
        changed = db.execute(
            "UPDATE products SET quantity = quantity - ? WHERE id = ? AND quantity >= ?",
            (it["quantity"], it["product_id"], it["quantity"]))
        if not changed:
            left = db.one("SELECT quantity FROM products WHERE id = ?", (it["product_id"],))
            left_qty = left["quantity"] if left else 0
            raise AppError(409, "not_enough_stock",
                           f"«{it['name']}» тауарынан қоймада тек {left_qty} дана бар. Себетті жаңартыңыз.")
        total += it["price"] * it["quantity"]
    order_id = db.insert(
        "INSERT INTO orders (user_id, username, total, status, created_at) VALUES (?, ?, ?, ?, ?)",
        (g.user["id"], g.user["username"], total, "new", now()))
    for it in items:
        db.insert(
            "INSERT INTO order_items (order_id, product_id, product_name, price, quantity) VALUES (?, ?, ?, ?, ?)",
            (order_id, it["product_id"], it["name"], it["price"], it["quantity"]))
        _log_move(db, {"id": it["product_id"], "name": it["name"]}, "out", it["quantity"])
    db.execute("DELETE FROM cart_items WHERE user_id = ?", (g.user["id"],))
    log.info("Жаңа тапсырыс №%s: %s, сома %s", order_id, g.user["username"], total)
    return jsonify(order=_one(db, order_id)), 201


@bp.get("")
@require()
def list_orders():
    db = get_db()
    if g.user["role"] in STAFF:
        orders = db.query(f"SELECT {ORDER_COLS} FROM orders ORDER BY id DESC LIMIT 100")
    else:
        orders = db.query(f"SELECT {ORDER_COLS} FROM orders WHERE user_id = ? ORDER BY id DESC LIMIT 100",
                          (g.user["id"],))
    return jsonify(orders=_with_items(db, orders))


@bp.patch("/<int:oid>")
@require(*STAFF)
def set_status(oid):
    data = parse(OrderStatusIn, json_body())
    db = get_db()
    _one(db, oid)
    db.execute("UPDATE orders SET status = ? WHERE id = ?", (data.status, oid))
    log.info("Тапсырыс №%s күйі: %s — %s", oid, data.status, g.user["username"])
    return jsonify(order=_one(db, oid))
