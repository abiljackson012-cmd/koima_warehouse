import logging

from flask import Blueprint, g, jsonify

from ..auth import USER_FIELDS, require
from ..db import get_db
from ..errors import AppError
from ..validation import RoleIn, parse
from . import json_body

log = logging.getLogger("warehouse")
bp = Blueprint("users", __name__, url_prefix="/api/users")


def _target(db, uid):
    user = db.one(f"SELECT {USER_FIELDS} FROM users WHERE id = ?", (uid,))
    if not user:
        raise AppError(404, "user_not_found", "Қолданушы табылмады.")
    return user


@bp.get("")
@require("admin")
def list_users():
    return jsonify(users=get_db().query(f"SELECT {USER_FIELDS} FROM users ORDER BY id"))


@bp.patch("/<int:uid>")
@require("admin")
def change_role(uid):
    data = parse(RoleIn, json_body())
    db = get_db()
    user = _target(db, uid)
    if user["id"] == g.user["id"]:
        raise AppError(409, "self_change", "Өз рөліңізді өзгертуге болмайды.")
    db.execute("UPDATE users SET role = ? WHERE id = ?", (data.role, uid))
    log.info("Рөл өзгертілді: %s → %s (%s)", user["username"], data.role, g.user["username"])
    return jsonify(user=_target(db, uid))


@bp.delete("/<int:uid>")
@require("admin")
def delete_user(uid):
    db = get_db()
    user = _target(db, uid)
    if user["id"] == g.user["id"]:
        raise AppError(409, "self_delete", "Өз аккаунтыңызды жоюға болмайды.")
    db.execute("DELETE FROM users WHERE id = ?", (uid,))
    log.info("Қолданушы жойылды: %s (%s)", user["username"], g.user["username"])
    return "", 204
