from fastapi.testclient import TestClient

from kiosk.app import create_app
from kiosk.catalog import Catalog, Product
from kiosk.scale import SimulatedScale
from kiosk.service import KioskService
from kiosk.tray import SimulatedTray

CATALOG = Catalog([Product("AGUA", "Agua", 250, 651.0)])


def make(with_sims: bool = True):
    scale = SimulatedScale(noise_g=0)
    tray = SimulatedTray(CATALOG, scale)
    svc = KioskService(CATALOG, tray, scale)
    app = (
        create_app(svc, tray, scale, run_loop=False)
        if with_sims
        else create_app(svc, run_loop=False)
    )
    return svc, TestClient(app)


def test_state_starts_on_w1():
    _, client = make()
    assert client.get("/api/state").json()["screen"] == "W1"


def test_invalid_action_returns_409_in_spanish():
    _, client = make()
    r = client.post("/api/pay")
    assert r.status_code == 409
    assert "no permitida" in r.json()["detail"]


def test_full_flow_over_http():
    svc, client = make()
    client.post("/api/start")
    client.post("/sim/tray", json={"skus": ["AGUA"]})
    for _ in range(3):
        svc.tick()
    assert client.post("/api/confirm").status_code == 200
    assert client.post("/api/pay").json()["screen"] == "QR"
    assert client.post("/sim/pay").json()["screen"] == "W4"


def test_unknown_sku_in_sim_tray_is_422():
    _, client = make()
    assert client.post("/sim/tray", json={"skus": ["X"]}).status_code == 422


def test_sim_catalog_lists_products():
    _, client = make()
    assert client.get("/sim/catalog").json() == [
        {"sku": "AGUA", "name": "Agua", "price_cents": 250, "weight_g": 651.0}
    ]


def test_help_lifecycle():
    _, client = make()
    assert client.post("/api/help").json()["help_pending"] is True
    assert [r["id"] for r in client.get("/api/help").json()] == [1]
    assert client.delete("/api/help/1").json() == []


def test_websocket_sends_snapshot():
    _, client = make()
    with client.websocket_connect("/ws") as ws:
        assert ws.receive_json()["screen"] == "W1"


def test_sim_routes_absent_without_simulators():
    _, client = make(with_sims=False)
    assert client.post("/sim/pay").status_code == 404
