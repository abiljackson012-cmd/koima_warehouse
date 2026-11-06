"""Бастапқы деректер: admin және manager аккаунттары (.env-тен) және демо-каталог."""
import logging

from werkzeug.security import generate_password_hash

from .db import get_db, now

log = logging.getLogger("warehouse")

# (артикул, атауы, санаты, бағасы ₸, қалдығы, минималды қалдық)
DEMO_PRODUCTS = [
    ("AZ-001", "Күріш «Баракат» 5 кг", "Азық-түлік", 3200, 40, 10),
    ("AZ-002", "Күріш 1 кг", "Азық-түлік", 620, 140, 50),
    ("AZ-003", "Макарон 500 г", "Азық-түлік", 450, 90, 30),
    ("AZ-004", "Қант 1 кг", "Азық-түлік", 520, 60, 20),
    ("AZ-005", "Тұз 1 кг", "Азық-түлік", 180, 70, 20),
    ("AZ-006", "Күнбағыс майы 1 л", "Азық-түлік", 980, 32, 40),
    ("AZ-007", "Ұн 2 кг", "Азық-түлік", 690, 25, 15),
    ("AZ-008", "Шай 100 г", "Азық-түлік", 780, 48, 20),
    ("AZ-009", "Кофе 100 г", "Азық-түлік", 1490, 12, 10),
    ("SU-001", "Сүт 1 л", "Сүт өнімдері", 540, 36, 20),
    ("SU-002", "Қаймақ 200 г", "Сүт өнімдері", 890, 9, 10),
    ("SU-003", "Ірімшік 300 г", "Сүт өнімдері", 1350, 22, 10),
    ("SU-004", "Таза су 1.5 л", "Сусындар", 240, 110, 40),
    ("SU-005", "Шырын 1 л", "Сусындар", 650, 0, 15),
    ("TS-001", "Кір жуғыш ұнтақ 3 кг", "Тұрмыстық", 2450, 18, 15),
    ("TS-002", "Ыдыс жуғыш сұйықтық 500 мл", "Тұрмыстық", 820, 27, 15),
    ("TS-003", "Сабын", "Тұрмыстық", 210, 80, 30),
    ("KS-001", "А4 қағаз (500 парақ)", "Кеңсе", 2100, 8, 25),
    ("KS-002", "Қалам (көк)", "Кеңсе", 150, 200, 50),
    ("EL-001", "USB кабель Type-C", "Электроника", 1200, 75, 20),
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
