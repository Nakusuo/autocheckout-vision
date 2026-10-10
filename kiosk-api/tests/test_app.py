from fastapi.testclient import TestClient
from payment_helpers import PUBLIC_PEM, FakeGateway
from starlette.websockets import WebSocketDisconnect

from kiosk.app import create_app, safe_tick
from kiosk.catalog import Catalog, Product
from kiosk.payments import JwtVerifier
from kiosk.scale import SimulatedScale
from kiosk.service import KioskService
from kiosk.tray import SimulatedTray

CATALOG = Catalog([Product("AGUA", "Agua", 250, 651.0)])


def make(with_sims: bool = True):
    scale = SimulatedScale(noise_g=0)
    tray = SimulatedTray(CATALOG, scale)
    gateway = FakeGateway()
    svc = KioskService(CATALOG, tray, scale, gateway, JwtVerifier(PUBLIC_PEM))
    app = (
        create_app(svc, tray, scale, run_loop=False)
        if with_sims
        else create_app(svc, run_loop=False)
    )
    return svc, TestClient(app), gateway


def test_state_starts_on_w1():
    _, client, _ = make()
    assert client.get("/api/state").json()["screen"] == "W1"


def test_invalid_action_returns_409_in_spanish():
    _, client, _ = make()
    r = client.post("/api/pay")
    assert r.status_code == 409
    assert "no permitida" in r.json()["detail"]


def test_full_flow_over_http():
    svc, client, gateway = make()
    client.post("/api/start")
    client.post("/sim/tray", json={"skus": ["AGUA"]})
    for _ in range(3):
        svc.tick()
    assert client.post("/api/confirm").status_code == 200
    assert client.post("/api/pay").json()["screen"] == "QR"
    gateway.paid = True
    svc.tick()
    assert client.get("/api/state").json()["screen"] == "W4"


def test_unknown_sku_in_sim_tray_is_422():
    _, client, _ = make()
    assert client.post("/sim/tray", json={"skus": ["X"]}).status_code == 422


def test_sim_catalog_lists_products():
    _, client, _ = make()
    assert client.get("/sim/catalog").json() == [
        {"sku": "AGUA", "name": "Agua", "price_cents": 250, "weight_g": 651.0}
    ]


def test_help_lifecycle():
    _, client, _ = make()
    assert client.post("/api/help").json()["help_pending"] is True
    assert [r["id"] for r in client.get("/api/help").json()] == [1]
    assert client.delete("/api/help/1").json() == []


def test_websocket_sends_snapshot():
    _, client, _ = make()
    with client.websocket_connect("/ws") as ws:
        assert ws.receive_json()["screen"] == "W1"


def test_sim_routes_absent_without_simulators():
    _, client, _ = make(with_sims=False)
    assert client.post("/sim/trap", json={"offset_g": 0}).status_code == 404


class ExplodingService:
    def tick(self) -> None:
        raise RuntimeError("boom")


def test_safe_tick_swallows_and_logs(caplog):
    safe_tick(ExplodingService())
    assert "Error en tick" in caplog.text


def test_foreign_origin_is_rejected():
    _, client, _ = make()
    r = client.post("/api/start", headers={"Origin": "https://evil.example"})
    assert r.status_code == 403


def test_kiosk_ui_origin_is_allowed():
    _, client, _ = make()
    r = client.post("/api/start", headers={"Origin": "http://localhost:5173"})
    assert r.status_code == 200


def test_ws_foreign_origin_is_closed():
    _, client, _ = make()
    try:
        with client.websocket_connect("/ws", headers={"origin": "https://evil.example"}) as ws:
            ws.receive_json()
        assert False, "Expected WebSocketDisconnect"
    except WebSocketDisconnect:
        pass


def test_trap_offset_out_of_bounds():
    _, client, _ = make()
    assert client.post("/sim/trap", json={"offset_g": 10000}).status_code == 422


def test_sim_pay_no_longer_exists():
    _, client, _ = make()
    assert client.post("/sim/pay").status_code == 404


def test_rescan_and_hidden_products_over_http():
    svc, client, _ = make()
    client.post("/api/start")
    assert client.post("/sim/tray", json={"skus": [], "hidden": ["AGUA"]}).status_code == 200
    for _ in range(3):
        svc.tick()
    # La balanza pesa un producto que la cámara no ve
    assert client.get("/api/state").json()["alert"] == "Revise su bandeja"
    r = client.post("/api/rescan")
    assert r.status_code == 200
    assert r.json()["screen"] == "W2"


def test_rescan_outside_scanning_is_409():
    _, client, _ = make()
    assert client.post("/api/rescan").status_code == 409
