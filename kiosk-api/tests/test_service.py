import pytest

from kiosk.catalog import Catalog, Product
from kiosk.checkout import TransitionError
from kiosk.scale import SimulatedScale
from kiosk.service import KioskService
from kiosk.tray import SimulatedTray

CATALOG = Catalog([Product("AGUA", "Agua", 250, 651.0), Product("CHOCO", "Chocolate", 280, 33.0)])


class FakeClock:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t


def make():
    clock = FakeClock()
    scale = SimulatedScale(noise_g=0)
    tray = SimulatedTray(CATALOG, scale)
    return KioskService(CATALOG, tray, scale, clock), tray, scale, clock


def ticks(svc: KioskService, n: int = 3) -> None:
    for _ in range(n):
        svc.tick()


def test_happy_path_w1_to_w4_and_auto_reset():
    svc, tray, _, clock = make()
    svc.start()
    tray.place(["AGUA"])
    ticks(svc)
    snap = svc.snapshot()
    assert snap["screen"] == "W2"
    assert snap["lines"] == [
        {"sku": "AGUA", "name": "Agua", "quantity": 1, "unit_price_cents": 250}
    ]
    assert snap["weight"] == {"ok": True, "diff_g": 0.0}

    svc.confirm()
    assert svc.snapshot()["can_pay"] is True
    svc.pay()
    assert svc.snapshot()["screen"] == "QR"
    svc.simulate_payment()
    assert svc.snapshot()["screen"] == "W4"

    clock.t = 9.9
    svc.tick()
    assert svc.snapshot()["screen"] == "W4"
    clock.t = 10.0
    svc.tick()
    assert svc.snapshot()["screen"] == "W1"


def test_not_stable_before_three_frames():
    svc, tray, _, _ = make()
    svc.start()
    tray.place(["AGUA"])
    ticks(svc, 2)
    assert svc.snapshot()["lines"] == []


def test_weight_mismatch_blocks_payment():
    svc, tray, scale, _ = make()
    svc.start()
    tray.place(["AGUA"])
    scale.set_trap(40.0)
    ticks(svc)
    assert svc.snapshot()["alert"] == "Revise su bandeja"
    svc.confirm()
    with pytest.raises(TransitionError):
        svc.pay()


def test_more_than_three_items():
    svc, tray, _, _ = make()
    svc.start()
    tray.place(["CHOCO"] * 4)
    ticks(svc)
    assert svc.snapshot()["alert"] == "Para más de 3 productos use la caja"
    with pytest.raises(TransitionError):
        svc.confirm()


def test_payment_timeout_returns_to_w3():
    svc, tray, _, clock = make()
    svc.start()
    tray.place(["AGUA"])
    ticks(svc)
    svc.confirm()
    svc.pay()
    clock.t = 120.0
    svc.tick()
    assert svc.snapshot()["screen"] == "W3"


def test_tray_change_in_w3_returns_to_w2():
    svc, tray, _, _ = make()
    svc.start()
    tray.place(["AGUA"])
    ticks(svc)
    svc.confirm()
    tray.place(["AGUA", "CHOCO"])
    ticks(svc)
    snap = svc.snapshot()
    assert snap["screen"] == "W2"
    assert snap["item_count"] == 2


class BrokenCamera:
    def detect(self) -> list[str]:
        raise OSError("cámara desconectada")


def test_sensor_failure_goes_out_of_service_and_recovers():
    scale = SimulatedScale(noise_g=0)
    svc = KioskService(CATALOG, BrokenCamera(), scale, FakeClock())
    svc.start()
    svc.tick()
    assert svc.snapshot()["screen"] == "FUERA_DE_SERVICIO"
    svc.recover()
    assert svc.snapshot()["screen"] == "W1"


def test_help_requests_lifecycle():
    svc, _, _, _ = make()
    req = svc.request_help()
    assert req == {"id": 1, "screen": "W1", "at": 0.0}
    assert svc.snapshot()["help_pending"] is True
    svc.resolve_help(1)
    assert svc.help_requests == []
    assert svc.snapshot()["help_pending"] is False
