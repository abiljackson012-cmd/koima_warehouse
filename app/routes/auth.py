import logging
import time

from flask import Blueprint, current_app, g, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

from ..auth import COOKIE, USER_FIELDS, create_token, require, revoke_current_token
from ..db import get_db, now
from ..errors import AppError
from ..validation import LoginIn, RegisterIn, parse
from . import json_body

log = logging.getLogger("warehouse")
bp = Blueprint("auth", __name__, url_prefix="/api/auth")

# Құпиясөзді таңдап бұзудан қорғау: 5 минутта 5 сәтсіз әрекеттен кейін уақытша бұғаттау.
MAX_FAILS, WINDOW = 5, 300
_fails: dict = {}
_DUMMY_HASH = generate_password_hash("dummy-password-for-timing")


def reset_limiter():
    _fails.clear()


def _key(username):
    return (request.remote_addr, username.lower())


def _check_limit(key):
    recent = [t for t in _fails.get(key, []) if time.time() - t < WINDOW]
    _fails[key] = recent
    if len(recent) >= MAX_FAILS:
        raise AppError(429, "too_many_attempts", "Тым көп сәтсіз әрекет. 5 минуттан кейін қайталап көріңіз.")


@bp.post("/register")
def register():
    data = parse(RegisterIn, json_body())
    db = get_db()
    if db.one("SELECT id FROM users WHERE lower(username) = ?", (data.username.lower(),)):
        raise AppError(409, "username_taken", "Бұл логин бос емес. Басқа логин таңдаңыз.",
                       [{"field": "username", "message": "Бұл логин бос емес."}])
    if db.one("SELECT id FROM users WHERE email = ?", (data.email,)):
        raise AppError(409, "email_taken", "Бұл email-мен аккаунт бұрыннан бар.",
                       [{"field": "email", "message": "Бұл email тіркелген."}])
    uid = db.insert(
        "INSERT INTO users (username, email, password_hash, role, created_at) VALUES (?, ?, ?, 'buyer', ?)",
        (data.username, data.email, generate_password_hash(data.password), now()),
    )
    user = db.one(f"SELECT {USER_FIELDS} FROM users WHERE id = ?", (uid,))
    log.info("Жаңа қолданушы тіркелді: %s", user["username"])
    return jsonify(user=user), 201


@bp.post("/login")
def login():
    data = parse(LoginIn, json_body())
    key = _key(data.username)
    _check_limit(key)
    db = get_db()
    row = db.one("SELECT * FROM users WHERE lower(username) = ? OR email = ?",
                 (data.username.lower(), data.username.lower()))
    ok = check_password_hash(row["password_hash"] if row else _DUMMY_HASH, data.password)
    if not (row and ok):
        _fails.setdefault(key, []).append(time.time())
        log.warning("Сәтсіз кіру әрекеті: %s", data.username)
        raise AppError(401, "bad_credentials", "Логин немесе құпиясөз қате. Қайта тексеріп көріңіз.")
    _fails.pop(key, None)

    token, exp = create_token(row["id"])
    resp = jsonify(user={k: row[k] for k in ("id", "username", "email", "role", "created_at")})
    resp.set_cookie(COOKIE, token, httponly=True, samesite="Lax", expires=exp,
                    secure=current_app.config["COOKIE_SECURE"])
    log.info("Кірді: %s (%s)", row["username"], row["role"])
    return resp


@bp.post("/logout")
@require()
def logout():
    revoke_current_token()
    resp = jsonify(message="Жүйеден шықтыңыз.")
    resp.delete_cookie(COOKIE)
    log.info("Шықты: %s", g.user["username"])
    return resp


@bp.get("/me")
@require()
def me():
    return jsonify(user=g.user)
