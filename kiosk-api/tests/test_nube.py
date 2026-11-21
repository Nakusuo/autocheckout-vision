"""Quiosco publicado en internet: orígenes extra, clave de caja e interfaz servida por la API."""

import pytest
from fastapi.testclient import TestClient
from payment_helpers import FakeGateway

from kiosk.__main__ import cloud_settings
from kiosk.app import create_app
from kiosk.catalog import Catalog, Product
from kiosk.scale import SimulatedScale
from kiosk.service import KioskService
from kiosk.tray import SimulatedTray

CATALOG = Catalog([Product("AGUA", "Agua", 250, 651.0)])
SITE = "https://usuario-autocaja.hf.space"
KEY = "k" * 20


def make(**options) -> TestClient:
    tray = SimulatedTray(CATALOG, SimulatedScale(noise_g=0))
    service = KioskService(CATALOG, tray, None, FakeGateway(), None)
    return TestClient(create_app(service, run_loop=False, **options))


CAJA_ROUTES = [
    ("GET", "/api/help"),
    ("DELETE", "/api/help/1"),
    ("GET", "/api/alerts"),
    ("DELETE", "/api/alerts/1"),
    ("GET", "/api/sales"),
    ("POST", "/api/recover"),
    ("POST", "/api/recalibrate"),
    ("POST", "/api/caja/accept-payment"),
]


@pytest.mark.parametrize(("method", "path"), CAJA_ROUTES)
def test_cashier_routes_require_the_key(method, path):
    http = make(caja_key=KEY)
    assert http.request(method, path).status_code == 401
    assert http.request(method, path, headers={"X-Caja-Key": "otra-clave-larga!!"}).status_code == 401
    assert http.request(method, path, headers={"X-Caja-Key": KEY}).status_code != 401


def test_customer_routes_stay_open_with_a_cashier_key():
    http = make(caja_key=KEY)
    assert http.get("/api/state").status_code == 200
    assert http.post("/api/help").status_code == 200  # el cliente pide ayuda sin clave
    assert http.get("/api/help", headers={"X-Caja-Key": KEY}).json()[0]["id"] == 1


def test_without_a_key_cashier_routes_are_open_like_the_local_kiosk():
    assert make().get("/api/help").status_code == 200


def test_extra_origin_is_accepted_and_others_still_rejected():
    http = make(allowed_origins={SITE})
    assert http.post("/api/start", headers={"Origin": SITE}).status_code == 200
    assert http.post("/api/start", headers={"Origin": "https://otro.test"}).status_code == 403
    with http.websocket_connect("/ws", headers={"Origin": SITE}) as ws:
        assert ws.receive_json()["screen"] == "W2"  # el POST de arriba ya empezó la compra


def test_own_https_site_is_accepted_without_listing_it():
    http = make()
    host = "autocaja-123.us-central1.run.app"
    ok = http.post("/api/start", headers={"Origin": f"https://{host}", "Host": host})
    assert ok.status_code == 200
    # Por http no (DNS rebinding), ni otro sitio aunque sea https.
    assert http.post("/api/start", headers={"Origin": f"http://{host}", "Host": host}).status_code == 403
    assert http.post("/api/start", headers={"Origin": "https://otro.test", "Host": host}).status_code == 403


def test_api_serves_the_interface_with_security_headers(tmp_path):
    (tmp_path / "index.html").write_text('<div id="root"></div>')
    (tmp_path / "app.js").write_text("console.log(1)")
    http = make(ui_dir=tmp_path)
    for page in ("/", "/ayuda"):
        r = http.get(page)
        assert r.status_code == 200 and 'id="root"' in r.text
        assert r.headers["X-Frame-Options"] == "DENY"
        assert "frame-ancestors 'none'" in r.headers["Content-Security-Policy"]
    assert http.get("/app.js").text == "console.log(1)"
    assert http.get("/api/state").json()["screen"] == "W1"  # la API sigue antes que los archivos


def test_cloud_settings(tmp_path):
    assert cloud_settings({}) == (set(), None, None)
    (tmp_path / "index.html").write_text("x")
    env = {"KIOSK_ORIGINS": f" {SITE}/ ", "KIOSK_CAJA_KEY": KEY, "KIOSK_UI_DIR": str(tmp_path)}
    assert cloud_settings(env) == ({SITE}, KEY, tmp_path)


@pytest.mark.parametrize(
    ("env", "message"),
    [
        ({"KIOSK_ORIGINS": SITE}, "KIOSK_CAJA_KEY"),
        ({"K_SERVICE": "autocaja"}, "KIOSK_CAJA_KEY"),
        ({"KIOSK_PUBLICO": "on"}, "KIOSK_CAJA_KEY"),
        ({"KIOSK_ORIGINS": "http://inseguro.test", "KIOSK_CAJA_KEY": KEY}, "https"),
        ({"KIOSK_ORIGINS": f"{SITE}/ruta", "KIOSK_CAJA_KEY": KEY}, "sin ruta"),
        ({"KIOSK_CAJA_KEY": "corta"}, "16 caracteres"),
        ({"KIOSK_UI_DIR": "/no/existe"}, "index.html"),
    ],
)
def test_cloud_settings_rejects_unsafe_values(env, message):
    with pytest.raises(SystemExit, match=message):
        cloud_settings(env)
