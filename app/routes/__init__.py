from flask import request

from ..errors import AppError


def json_body() -> dict:
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise AppError(400, "invalid_json", "Сұраныс денесі дұрыс JSON нысаны болуы керек.")
    return data
