import logging

from flask import Blueprint, g, jsonify, request

from ..auth import require
from ..db import get_db, now
from ..errors import AppError
from ..validation import (MovementIn, MovementListQuery, ProductCreate, ProductListQuery, ProductPatch,
                          ProductUpdate, parse)
from . import json_body

log = logging.getLogger("warehouse")
bp = Blueprint("products", __name__, url_prefix="/api")

COLS = "id, sku, name, category, price, quantity, min_quantity, created_at"


def _out(p: dict) -> dict:
    p["low"] = p["quantity"] <= p["min_quantity"]
    return p


def _get_or_404(db, pid):
    p = db.one(f"SELECT {COLS} FROM products WHERE id = ?", (pid,))
    if not p:
        raise AppError(404, "product_not_found", "Тауар табылмады.")
    return p


def _check_sku_free(db, sku, exclude_id=None):
    row = db.one("SELECT id FROM products WHERE sku = ?", (sku,))
    if row and row["id"] != exclude_id:
        raise AppError(409, "sku_taken", "Бұл артикул бұрыннан бар. Басқа артикул енгізіңіз.",
                       [{"field": "sku", "message": "Артикул бос емес."}])


def _log_move(db, product, ptype, qty):
    db.insert(
        "INSERT INTO movements (product_id, product_name, user_id, username, type, quantity, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (product["id"], product["name"], g.user["id"], g.user["username"], ptype, qty, now()),
    )


@bp.get("/products")
@require()
def list_products():
    q = parse(ProductListQuery, request.args.to_dict())
    sql = f"SELECT {COLS} FROM products"
    if q.low == "1":
        sql += " WHERE quantity <= min_quantity"
    rows = get_db().query(sql + " ORDER BY id")
    if q.search:
        # SQLite lower() кириллицаны түсінбейді, сондықтан іздеуді Python жағында жасаймыз.
        s = q.search.casefold()
        rows = [r for r in rows if s in r["name"].casefold() or s in r["sku"].casefold()]
    total = len(rows)
    rows = rows[q.offset:q.offset + q.limit]
    return jsonify(products=[_out(r) for r in rows], total=total)


@bp.get("/products/<int:pid>")
@require()
def get_product(pid):
    return jsonify(product=_out(_get_or_404(get_db(), pid)))


@bp.post("/products")
@require("manager", "admin")
def create_product():
    data = parse(ProductCreate, json_body())
    db = get_db()
    _check_sku_free(db, data.sku)
    pid = db.insert(
        "INSERT INTO products (sku, name, category, price, quantity, min_quantity, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (data.sku, data.name, data.category, data.price, data.quantity, data.min_quantity, now()),
    )
    product = _get_or_404(db, pid)
    if data.quantity > 0:
        _log_move(db, product, "init", data.quantity)
    log.info("Тауар қосылды: %s (%s) — %s", product["name"], product["sku"], g.user["username"])
    return jsonify(product=_out(product)), 201


def _update(pid, fields: dict):
    db = get_db()
    product = _get_or_404(db, pid)
    if "sku" in fields:
        _check_sku_free(db, fields["sku"], exclude_id=pid)
    if fields:
        sets = ", ".join(f"{k} = ?" for k in fields)
        db.execute(f"UPDATE products SET {sets} WHERE id = ?", (*fields.values(), pid))
    log.info("Тауар өзгертілді: id=%s %s — %s", pid, list(fields), g.user["username"])
    return jsonify(product=_out(_get_or_404(db, product["id"])))


@bp.put("/products/<int:pid>")
@require("manager", "admin")
def replace_product(pid):
    return _update(pid, parse(ProductUpdate, json_body()).model_dump())


@bp.patch("/products/<int:pid>")
@require("manager", "admin")
def patch_product(pid):
    return _update(pid, parse(ProductPatch, json_body()).model_dump(exclude_none=True))


@bp.delete("/products/<int:pid>")
@require("admin")
def delete_product(pid):
    db = get_db()
    product = _get_or_404(db, pid)
    db.execute("DELETE FROM products WHERE id = ?", (pid,))
    log.info("Тауар жойылды: %s — %s", product["name"], g.user["username"])
    return "", 204


@bp.post("/products/<int:pid>/movements")
@require("manager", "admin")
def add_movement(pid):
    data = parse(MovementIn, json_body())
    db = get_db()
    product = _get_or_404(db, pid)
    if data.type == "in":
        db.execute("UPDATE products SET quantity = quantity + ? WHERE id = ?", (data.quantity, pid))
    else:
        # Шартты UPDATE ішінде тексереміз: екі сұраныс қатар келсе де қалдық минусқа кетпейді.
        changed = db.execute("UPDATE products SET quantity = quantity - ? WHERE id = ? AND quantity >= ?",
                             (data.quantity, pid, data.quantity))
        if not changed:
            current = _get_or_404(db, pid)["quantity"]
            raise AppError(409, "not_enough_stock", f"Қоймада тек {current} дана бар. Азырақ сан енгізіңіз.",
                           [{"field": "quantity", "message": f"Қалдық: {current}"}])
    _log_move(db, product, data.type, data.quantity)
    return jsonify(product=_out(_get_or_404(db, pid))), 201


@bp.get("/movements")
@require()
def list_movements():
    q = parse(MovementListQuery, request.args.to_dict())
    rows = get_db().query(
        "SELECT id, product_id, product_name, username, type, quantity, created_at "
        "FROM movements ORDER BY id DESC LIMIT ?", (q.limit,))
    return jsonify(movements=rows)


@bp.get("/stats")
@require()
def stats():
    row = get_db().one(
        "SELECT COUNT(*) AS products, COALESCE(SUM(quantity), 0) AS total_quantity, "
        "COALESCE(SUM(quantity * price), 0) AS total_value, "
        "COALESCE(SUM(CASE WHEN quantity <= min_quantity THEN 1 ELSE 0 END), 0) AS low_stock FROM products")
    return jsonify(stats=row)
