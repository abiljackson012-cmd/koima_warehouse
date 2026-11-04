"""JWT авторизациясы және рөлдерді тексеру."""
import uuid
from datetime import datetime, timedelta, timezone
from functools import wraps

import jwt
from flask import current_app, g, request

from .db import get_db, now
from .errors import AppError

COOKIE = "token"
USER_FIELDS = "id, username, email, role, created_at"


def create_token(user_id: int):
    exp = datetime.now(timezone.utc) + timedelta(hours=current_app.config["TOKEN_HOURS"])
    payload = {"sub": str(user_id), "jti": uuid.uuid4().hex, "exp": exp}
    token = jwt.encode(payload, current_app.config["SECRET_KEY"], algorithm="HS256")
    return token, exp


def _read_token():
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        return header[7:].strip()
    return request.cookies.get(COOKIE)


def authenticate():
    token = _read_token()
    if not token:
        raise AppError(401, "not_authenticated", "Алдымен жүйеге кіріңіз.")
    try:
        payload = jwt.decode(
            token, current_app.config["SECRET_KEY"], algorithms=["HS256"],
            options={"require": ["exp", "jti", "sub"]},
        )
    except jwt.ExpiredSignatureError:
        raise AppError(401, "token_expired", "Сессия мерзімі өтті. Қайта кіріңіз.") from None
    except jwt.InvalidTokenError:
        raise AppError(401, "invalid_token", "Токен жарамсыз. Қайта кіріңіз.") from None

    db = get_db()
    if db.one("SELECT jti FROM revoked_tokens WHERE jti = ?", (payload["jti"],)):
        raise AppError(401, "token_revoked", "Сіз жүйеден шыққансыз. Қайта кіріңіз.")
    user = db.one(f"SELECT {USER_FIELDS} FROM users WHERE id = ?", (int(payload["sub"]),))
    if not user:
        raise AppError(401, "user_not_found", "Аккаунт табылмады. Қайта кіріңіз.")
    g.user = user
    g.token_payload = payload
    return user


def require(*roles):
    """Маршрутты қорғайды. Рөл көрсетілмесе, жүйеге кірген кез келген қолданушыға рұқсат."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            user = authenticate()
            if roles and user["role"] not in roles:
                raise AppError(403, "forbidden", "Бұл әрекетке рұқсатыңыз жоқ.")
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def revoke_current_token():
    db = get_db()
    exp = datetime.fromtimestamp(g.token_payload["exp"], timezone.utc).isoformat(timespec="seconds")
    db.execute("DELETE FROM revoked_tokens WHERE expires_at < ?", (now(),))
    db.execute("INSERT INTO revoked_tokens (jti, expires_at) VALUES (?, ?) ON CONFLICT (jti) DO NOTHING",
               (g.token_payload["jti"], exp))
