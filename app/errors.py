"""Қателерді өңдеу: барлық қате бірдей JSON форматымен қайтады.

{"error": {"code": "...", "message": "...", "details": [{"field": "...", "message": "..."}]}}
"""
import logging

from flask import jsonify
from werkzeug.exceptions import HTTPException

from .db import ConflictError

log = logging.getLogger("warehouse")


class AppError(Exception):
    def __init__(self, status: int, code: str, message: str, details=None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.details = details


def _response(status, code, message, details=None):
    body = {"error": {"code": code, "message": message}}
    if details:
        body["error"]["details"] = details
    return jsonify(body), status


_HTTP_MESSAGES = {
    404: ("not_found", "Сұралған ресурс табылмады."),
    405: ("method_not_allowed", "Бұл әдіс (method) осы мекенжайға жарамайды."),
    413: ("too_large", "Сұраныс тым үлкен."),
}


def register_errors(app):
    @app.errorhandler(AppError)
    def handle_app_error(e):
        return _response(e.status, e.code, e.message, e.details)

    @app.errorhandler(ConflictError)
    def handle_conflict(e):
        log.warning("DB conflict: %s", e)
        return _response(409, "conflict", "Бұл деректер бұрыннан бар немесе байланысты жазбаларға қайшы келеді.")

    @app.errorhandler(HTTPException)
    def handle_http(e):
        code, message = _HTTP_MESSAGES.get(e.code, ("http_error", e.description or "Сұраныс қатесі."))
        return _response(e.code, code, message)

    @app.errorhandler(Exception)
    def handle_unexpected(e):
        # Толық себебі лог файлына жазылады (debugging үшін), қолданушыға жалпы хабар көрсетіледі.
        log.exception("Күтпеген қате: %s", e)
        return _response(500, "server_error", "Серверде күтпеген қате болды. Кейінірек қайталап көріңіз.")
