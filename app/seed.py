"""Бастапқы деректер: admin және manager аккаунттары (.env-тен) және қалау бойынша демо-тауарлар."""
import logging

from werkzeug.security import generate_password_hash

from .db import get_db, now

log = logging.getLogger("warehouse")

DEMO_PRODUCTS = [
    ("AZ-001", "Күріш 1 кг", "Азық-түлік", 620, 140, 50),
    ("AZ-002", "Күнбағыс майы 1 л", "Азық-түлік", 980, 32, 40),
    ("TS-010", "Кір жуғыш ұнтақ 3 кг", "Тұрмыстық", 2450, 18, 15),
    ("EL-204", "USB кабель Type-C", "Электроника", 1200, 75, 20),
    ("KS-501", "А4 қағаз (500 парақ)", "Кеңсе", 2100, 8, 25),
]


def seed_users(config):
    db = get_db()
    for role in ("admin", "manager"):
        name = config[f"{role.upper()}_USERNAME"]
        password = config[f"{role.upper()}_PASSWORD"]
        if not name or not password:
            continue
        if db.one("SELECT id FROM users WHERE lower(username) = ?", (name.lower(),)):
            continue
        db.insert(
            "INSERT INTO users (username, email, password_hash, role, created_at) VALUES (?, ?, ?, ?, ?)",
            (name, config[f"{role.upper()}_EMAIL"].lower(), generate_password_hash(password), role, now()),
        )
        log.info("Бастапқы аккаунт жасалды: %s (%s)", name, role)
    db.commit()


def seed_demo_products():
    db = get_db()
    if db.one("SELECT id FROM products LIMIT 1"):
        return
    for sku, name, cat, price, qty, minq in DEMO_PRODUCTS:
        db.insert(
            "INSERT INTO products (sku, name, category, price, quantity, min_quantity, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)", (sku, name, cat, price, qty, minq, now()))
    db.commit()
