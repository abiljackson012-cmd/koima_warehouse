import pytest

from app import create_app
from app.routes.auth import reset_limiter

ADMIN = ("admin_test", "AdminPass123")
MANAGER = ("manager_test", "ManagerPass123")


@pytest.fixture()
def app(tmp_path):
    reset_limiter()
    return create_app({
        "TESTING": True,
        "SECRET_KEY": "test-secret-key-for-pytest-only-0123456789",
        "DATABASE_URL": f"sqlite:///{tmp_path / 'test.db'}",
        "LOG_FILE": None,
        "ADMIN_USERNAME": ADMIN[0], "ADMIN_PASSWORD": ADMIN[1],
        "MANAGER_USERNAME": MANAGER[0], "MANAGER_PASSWORD": MANAGER[1],
        "SEED_DEMO_DATA": False,
    })


def _login(app, creds):
    c = app.test_client()
    r = c.post("/api/auth/login", json={"username": creds[0], "password": creds[1]})
    assert r.status_code == 200, r.get_json()
    return c


@pytest.fixture()
def anon(app):
    return app.test_client()


@pytest.fixture()
def admin(app):
    return _login(app, ADMIN)


@pytest.fixture()
def manager(app):
    return _login(app, MANAGER)


@pytest.fixture()
def user(app):
    c = app.test_client()
    r = c.post("/api/auth/register", json={"username": "student", "email": "student@example.com",
                                           "password": "Secret123"})
    assert r.status_code == 201
    r = c.post("/api/auth/login", json={"username": "student", "password": "Secret123"})
    assert r.status_code == 200
    return c


GOOD = {"sku": "TS-1", "name": "Сусын", "category": "Азық", "price": 500, "min_quantity": 5, "quantity": 10}


@pytest.fixture()
def product(manager):
    r = manager.post("/api/products", json=GOOD)
    assert r.status_code == 201
    return r.get_json()["product"]
