import logging
import os
from logging.handlers import RotatingFileHandler

from flask import Flask, jsonify, send_from_directory

from . import db
from .config import load_config
from .errors import register_errors
from .seed import seed_demo_products, seed_users


def _setup_logging(app):
    """Логтар консольге және logs/app.log файлына жазылады (debugging үшін)."""
    level = getattr(logging, str(app.config["LOG_LEVEL"]).upper(), logging.INFO)
    log = logging.getLogger("warehouse")
    log.setLevel(level)
    if log.handlers:
        return
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    console = logging.StreamHandler()
    console.setFormatter(fmt)
    log.addHandler(console)
    path = app.config.get("LOG_FILE")
    if path:
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            fh = RotatingFileHandler(path, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
            fh.setFormatter(fmt)
            log.addHandler(fh)
        except OSError:
            log.warning("Лог файлын ашу мүмкін болмады: %s", path)


def create_app(overrides=None):
    app = Flask(__name__, static_folder="static", static_url_path="")
    app.config.update(load_config())
    if overrides:
        app.config.update(overrides)
    if not app.config["SECRET_KEY"] or len(app.config["SECRET_KEY"]) < 32:
        raise RuntimeError("SECRET_KEY орнатылмаған немесе тым қысқа. .env файлына кемінде 32 таңба жазыңыз.")
    app.config["MAX_CONTENT_LENGTH"] = 4 * 1024 * 1024  # сурет жүктеуге жеткілікті
    app.config.setdefault("UPLOAD_DIR", os.path.join(app.static_folder, "uploads"))
    os.makedirs(app.config["UPLOAD_DIR"], exist_ok=True)

    _setup_logging(app)
    db.init_app(app)
    register_errors(app)

    from .routes import auth, cart, orders, products, users
    for module in (auth, products, users, cart, orders):
        app.register_blueprint(module.bp)

    @app.get("/")
    def index():
        return send_from_directory(app.static_folder, "index.html")

    @app.get("/api/health")
    def health():
        return jsonify(status="ok")

    with app.app_context():
        db.init_db()
        seed_users(app.config)
        if app.config["SEED_DEMO_DATA"]:
            seed_demo_products()
    return app
