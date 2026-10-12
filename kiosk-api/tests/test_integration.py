"""Modo cámara de punta a punta: bucle real en otro hilo, reconocedor con cuadros grabados y pago."""

import threading
import time

import pytest
from fastapi.testclient import TestClient
from payment_helpers import PUBLIC_PEM, FakeGateway
from test_recognizer import BLUE, RED, fake_embed, gallery_of, tray

import kiosk.app as app_module
from kiosk.app import create_app
from kiosk.catalog import Catalog, Product
from kiosk.payments import JwtVerifier
from kiosk.recognizer import SimilarityDetector
from kiosk.scale import SimulatedScale
from kiosk.service import KioskService

CATALOG = Catalog(
    [Product("ROJO", "Galleta roja", 150, 30.0), Product("AZUL", "Galleta azul", 130, 25.0)]
)


class Webcam:
    """Cámara grabada que se puede cambiar en vivo: lo que «hay frente a la cámara» ahora."""

    def __init__(self):
        self.frame = tray()

    def read(self):
        return self.frame.copy()


def wait_for(client: TestClient, screen: str, timeout: float = 5.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        snap = client.get("/api/state").json()
        if snap["screen"] == screen:
            return snap
        time.sleep(0.05)
    raise AssertionError(f"El quiosco no llegó a {screen}: {snap}")


@pytest.fixture
def camera_kiosk(monkeypatch):
    monkeypatch.setattr(app_module, "TICK_S", 0.02)
    cam = Webcam()
    gallery = gallery_of(("ROJO", [RED]), ("AZUL", [BLUE]))
    detector = SimilarityDetector(fake_embed, gallery, cam, threshold=1.2, warmup_frames=3)
    gateway = FakeGateway()
    service = KioskService(CATALOG, detector, None, gateway, JwtVerifier(PUBLIC_PEM))
    app = create_app(service, threaded_sensing=True)
    with TestClient(app) as client:  # arranca el bucle real (lifespan)
        yield client, cam, gateway


def test_camera_mode_w1_to_w4_one_product_at_a_time(camera_kiosk):
    client, cam, gateway = camera_kiosk
    time.sleep(0.2)  # W1: aprende la bandeja vacía
    assert client.get("/api/state").json()["camera"] is True
    client.post("/api/start")

    for color in (RED, BLUE):
        cam.frame = tray(color)  # el cliente pasa el producto…
        time.sleep(0.3)
        cam.frame = tray()  # …y lo retira
        time.sleep(0.3)
    snap = wait_for(client, "W2")
    assert {line["sku"]: line["quantity"] for line in snap["lines"]} == {"ROJO": 1, "AZUL": 1}
    assert snap["total_cents"] == 280

    client.post("/api/confirm")
    client.post("/api/pay")
    wait_for(client, "QR")
    gateway.paid = True
    snap = wait_for(client, "W4")
    assert snap["total_cents"] == 280


def test_camera_mode_two_products_at_once_blocks_payment(camera_kiosk):
    client, cam, _ = camera_kiosk
    time.sleep(0.2)
    client.post("/api/start")
    both = tray()
    both[5:40, 5:40] = RED
    both[75:110, 115:150] = BLUE
    cam.frame = both
    time.sleep(0.4)
    snap = client.get("/api/state").json()
    assert snap["alert"] == "Hay un producto que no reconocemos"
    assert client.post("/api/confirm").status_code == 409


def test_screen_keeps_answering_while_a_frame_is_slow(monkeypatch):
    """Un cuadro lento (cámara/IA) no congela la API: el estado responde enseguida."""
    monkeypatch.setattr(app_module, "TICK_S", 0.02)

    class SlowCamera:
        def detect(self):
            time.sleep(0.5)
            return []

        def recalibrate(self):
            pass

    service = KioskService(CATALOG, SlowCamera(), None, FakeGateway(), JwtVerifier(PUBLIC_PEM))
    with TestClient(create_app(service, threaded_sensing=True)) as client:
        time.sleep(0.1)  # el hilo ya está dentro de detect()
        start = time.monotonic()
        assert client.get("/api/state").status_code == 200
        assert time.monotonic() - start < 0.3


def test_recalibrate_while_detecting_in_another_thread_never_fails():
    cam = Webcam()
    cam.frame = tray(RED)
    detector = SimilarityDetector(
        fake_embed, gallery_of(("ROJO", [RED])), cam, threshold=1.2, warmup_frames=2
    )
    errors: list[BaseException] = []
    stop = threading.Event()

    def keep_detecting():
        while not stop.is_set():
            try:
                detector.detect()
            except BaseException as e:  # noqa: BLE001 - la prueba recoge cualquier fallo
                errors.append(e)

    worker = threading.Thread(target=keep_detecting)
    worker.start()
    for _ in range(200):
        detector.recalibrate()
    stop.set()
    worker.join(timeout=5)
    assert errors == []


def test_sim_scale_can_be_switched_only_on_w1():
    scale = SimulatedScale(noise_g=0)
    from kiosk.tray import SimulatedTray

    tray_ = SimulatedTray(CATALOG, scale)
    service = KioskService(CATALOG, tray_, scale, FakeGateway(), JwtVerifier(PUBLIC_PEM))
    client = TestClient(create_app(service, tray_, scale, run_loop=False))
    assert client.post("/sim/scale", json={"enabled": False}).json()["weight_enabled"] is False
    assert client.post("/sim/scale", json={"enabled": True}).json()["weight_enabled"] is True
    client.post("/api/start")
    assert client.post("/sim/scale", json={"enabled": False}).status_code == 409
