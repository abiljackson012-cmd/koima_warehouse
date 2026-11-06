from flask import Blueprint, g, jsonify

from ..auth import require
from ..db import get_db
from ..errors import AppError
from ..validation import CartAddIn, CartSetIn, parse
from . import image_url, json_body

bp = Blueprint("cart", __name__, url_prefix="/api/cart")


def _cart(db):
    rows = db.query(
        "SELECT c.product_id, c.quantity, p.name, p.sku, p.price, p.quantity AS stock, p.image "
        "FROM cart_items c JOIN products p ON p.id = c.product_id WHERE c.user_id = ? ORDER BY c.id",
        (g.user["id"],),
    )
    items = [{
        "product_id": r["product_id"], "name": r["name"], "sku": r["sku"], "price": r["price"],
        "quantity": r["quantity"], "stock": r["stock"], "image_url": image_url(r["image"]),
        "subtotal": r["price"] * r["quantity"], "available": r["stock"] >= r["quantity"],
    } for r in rows]
    return {"items": items, "total": sum(i["subtotal"] for i in items),
            "count": sum(i["quantity"] for i in items)}


def _set_qty(db, pid, qty):
    """Себеттегі санды орнатады. 0 болса, тауарды себеттен алып тастайды. Қалдық жеткілікті болуы шарт."""
    product = db.one("SELECT id, name, quantity FROM products WHERE id = ?", (pid,))
    if not product:
        raise AppError(404, "product_not_found", "Тауар табылмады.")
    if qty > product["quantity"]:
        if product["quantity"] == 0:
            raise AppError(409, "out_of_stock", "Бұл тауар қоймада таусылған.")
        raise AppError(409, "not_enough_stock", f"Қоймада тек {product['quantity']} дана бар.")
    existing = db.one("SELECT id FROM cart_items WHERE user_id = ? AND product_id = ?", (g.user["id"], pid))
    if qty == 0:
        if existing:
            db.execute("DELETE FROM cart_items WHERE id = ?", (existing["id"],))
    elif existing:
        db.execute("UPDATE cart_items SET quantity = ? WHERE id = ?", (qty, existing["id"]))
    else:
        db.insert("INSERT INTO cart_items (user_id, product_id, quantity) VALUES (?, ?, ?)",
                  (g.user["id"], pid, qty))


@bp.get("")
@require()
def get_cart():
    return jsonify(cart=_cart(get_db()))


@bp.post("")
@require()
def add_item():
    data = parse(CartAddIn, json_body())
    db = get_db()
    current = db.one("SELECT quantity FROM cart_items WHERE user_id = ? AND product_id = ?",
                     (g.user["id"], data.product_id))
    new_qty = (current["quantity"] if current else 0) + data.quantity
    if new_qty > 1000:
        raise AppError(422, "validation_error", "Бір тауардың саны 1000-нан аспауы керек.")
    _set_qty(db, data.product_id, new_qty)
    return jsonify(cart=_cart(db)), 201


@bp.patch("/<int:pid>")
@require()
def set_qty(pid):
    data = parse(CartSetIn, json_body())
    db = get_db()
    _set_qty(db, pid, data.quantity)
    return jsonify(cart=_cart(db))


@bp.delete("/<int:pid>")
@require()
def remove_item(pid):
    db = get_db()
    if db.execute("DELETE FROM cart_items WHERE user_id = ? AND product_id = ?", (g.user["id"], pid)) == 0:
        raise AppError(404, "not_in_cart", "Себетте мұндай тауар жоқ.")
    return jsonify(cart=_cart(db))
