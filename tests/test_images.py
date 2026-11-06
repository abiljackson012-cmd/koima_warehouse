"""Тауар суреттері: жүктеу, файл түрін тексеру, өлшем шегі, рұқсат, файлды жою."""
import io
import os

from conftest import GOOD

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
JPG = b"\xff\xd8\xff\xe0" + b"\x00" * 64
WEBP = b"RIFF" + b"\x00\x00\x00\x00" + b"WEBP" + b"\x00" * 16


def _product(manager):
    return manager.post("/api/products", json=GOOD).get_json()["product"]


def _upload(client, pid, data, name="a.png"):
    return client.post(f"/api/products/{pid}/image", data={"image": (io.BytesIO(data), name)})


def test_manager_uploads_png_and_url_is_saved(app, manager):
    p = _product(manager)
    r = _upload(manager, p["id"], PNG)
    assert r.status_code == 200
    url = r.get_json()["product"]["image_url"]
    assert url.startswith("/uploads/") and url.endswith(".png")
    assert os.path.exists(os.path.join(app.config["UPLOAD_DIR"], url.split("/")[-1]))
    assert manager.get(f"/api/products/{p['id']}").get_json()["product"]["image_url"] == url


def test_jpg_and_webp_accepted_and_replaced(app, manager):
    p = _product(manager)
    first = _upload(manager, p["id"], PNG).get_json()["product"]["image_url"]
    assert _upload(manager, p["id"], JPG, "a.jpg").status_code == 200
    assert _upload(manager, p["id"], WEBP, "a.webp").status_code == 200
    assert not os.path.exists(os.path.join(app.config["UPLOAD_DIR"], first.split("/")[-1]))


def test_fake_file_type_rejected(manager):
    p = _product(manager)
    r = _upload(manager, p["id"], b"<html>not an image</html>", "evil.png")
    assert r.status_code == 422 and r.get_json()["error"]["code"] == "validation_error"


def test_file_too_large_rejected(manager):
    p = _product(manager)
    big = b"\x89PNG\r\n\x1a\n" + b"0" * (3 * 1024 * 1024 + 10)
    assert _upload(manager, p["id"], big).status_code == 413


def test_buyer_cannot_upload(manager, user):
    p = _product(manager)
    assert _upload(user, p["id"], PNG).status_code == 403


def test_missing_file_rejected(manager):
    p = _product(manager)
    assert manager.post(f"/api/products/{p['id']}/image", data={}).status_code == 422


def test_upload_to_unknown_product(manager):
    assert _upload(manager, 999, PNG).status_code == 404


def test_deleting_product_removes_image_file(app, manager, admin):
    p = _product(manager)
    url = _upload(manager, p["id"], PNG).get_json()["product"]["image_url"]
    path = os.path.join(app.config["UPLOAD_DIR"], url.split("/")[-1])
    assert os.path.exists(path)
    assert admin.delete(f"/api/products/{p['id']}").status_code == 204
    assert not os.path.exists(path)
