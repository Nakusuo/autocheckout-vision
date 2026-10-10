import pytest
from payment_helpers import PUBLIC_PEM, FakeGateway

from kiosk.catalog import Catalog, Product
from kiosk.checkout import TransitionError
from kiosk.payments import JwtVerifier
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
    gateway = FakeGateway()
    svc = KioskService(CATALOG, tray, scale, gateway, JwtVerifier(PUBLIC_PEM), clock)
    return svc, tray, scale, clock, gateway


def ticks(svc: KioskService, n: int = 3) -> None:
    for _ in range(n):
        svc.tick()


def test_happy_path_w1_to_w4_and_auto_reset():
    svc, tray, _, clock, gateway = make()
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
    assert svc.snapshot()["qr_payload"] == "https://localhost:8443/pay/ch_1"
    assert gateway.amounts == [250]
    gateway.paid = True
    svc.tick()
    assert svc.snapshot()["screen"] == "W4"

    clock.t = 9.9
    svc.tick()
    assert svc.snapshot()["screen"] == "W4"
    clock.t = 10.0
    svc.tick()
    assert svc.snapshot()["screen"] == "W1"


def test_paid_sale_issues_one_simulated_receipt():
    svc, tray, _, _, gateway = make()
    svc.start()
    tray.place(["AGUA", "AGUA"])
    ticks(svc)
    svc.confirm()
    svc.pay()
    gateway.paid = True
    svc.tick()
    svc.tick()
    assert svc.snapshot()["screen"] == "W4"
    assert len(svc.pos.receipts) == 1
    receipt = svc.pos.receipts[0]
    assert receipt["charge_id"] == "ch_1"
    assert receipt["reference"] == "venta-1"
    assert receipt["total_cents"] == 500
    assert receipt["lines"] == [
        {"sku": "AGUA", "name": "Agua", "quantity": 2, "unit_price_cents": 250}
    ]


def test_session_metrics_from_start_to_paid():
    svc, tray, scale, clock, gateway = make()
    clock.t = 5.0
    svc.start()
    tray.place(["AGUA"])
    scale.set_trap(40.0)
    ticks(svc)
    ticks(svc)  # la alerta de peso sigue: cuenta una sola vez
    scale.set_trap(0.0)
    ticks(svc)
    svc.confirm()
    svc.correct()
    ticks(svc)
    svc.confirm()
    svc.request_help()
    svc.pay()
    clock.t = 35.0
    gateway.paid = True
    svc.tick()

    [session] = svc.sessions.sessions
    assert session["outcome"] == "paid"
    assert session["duration_s"] == 30.0
    assert session["weight_alerts"] == 1
    assert session["corrections"] == 1
    assert session["help_requested"] is True
    assert session["items"] == 1
    assert session["total_cents"] == 250


def test_session_ends_as_fault_when_sensor_fails():
    scale = SimulatedScale(noise_g=0)
    svc = KioskService(CATALOG, BrokenCamera(), scale, FakeGateway(), JwtVerifier(PUBLIC_PEM), FakeClock())
    svc.start()
    svc.tick()
    assert [s["outcome"] for s in svc.sessions.sessions] == ["fault"]


def test_not_stable_before_three_frames():
    svc, tray, _, _, _ = make()
    svc.start()
    tray.place(["AGUA"])
    ticks(svc, 2)
    assert svc.snapshot()["lines"] == []


def test_weight_mismatch_blocks_payment():
    svc, tray, scale, _, _ = make()
    svc.start()
    tray.place(["AGUA"])
    scale.set_trap(40.0)
    ticks(svc)
    assert svc.snapshot()["alert"] == "Revise su bandeja"
    svc.confirm()
    with pytest.raises(TransitionError):
        svc.pay()


def test_more_than_three_items():
    svc, tray, _, _, _ = make()
    svc.start()
    tray.place(["CHOCO"] * 4)
    ticks(svc)
    assert svc.snapshot()["alert"] == "Para más de 3 productos use la caja"
    with pytest.raises(TransitionError):
        svc.confirm()


def test_payment_timeout_returns_to_w3():
    svc, tray, _, clock, _ = make()
    svc.start()
    tray.place(["AGUA"])
    ticks(svc)
    svc.confirm()
    svc.pay()
    clock.t = 120.0
    svc.tick()
    assert svc.snapshot()["screen"] == "W3"


def test_tray_change_in_w3_returns_to_w2():
    svc, tray, _, _, _ = make()
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
    svc = KioskService(CATALOG, BrokenCamera(), scale, FakeGateway(), JwtVerifier(PUBLIC_PEM), FakeClock())
    svc.start()
    svc.tick()
    assert svc.snapshot()["screen"] == "FUERA_DE_SERVICIO"
    svc.recover()
    assert svc.snapshot()["screen"] == "W1"


def test_help_requests_lifecycle():
    svc, _, _, _, _ = make()
    req = svc.request_help()
    assert req == {"id": 1, "screen": "W1", "at": 0.0}
    assert svc.snapshot()["help_pending"] is True
    svc.resolve_help(1)
    assert svc.help_requests == []
    assert svc.snapshot()["help_pending"] is False


def paying(amount_skus=("AGUA",)):
    svc, tray, _, clock, gateway = make()
    svc.start()
    tray.place(list(amount_skus))
    ticks(svc)
    svc.confirm()
    svc.pay()
    return svc, clock, gateway


def test_wrong_amount_does_not_complete_sale():
    svc, _, gateway = paying()
    gateway.paid = True
    gateway.paid_amount = 1
    svc.tick()
    assert svc.snapshot()["screen"] == "QR"


def test_gateway_down_on_pay_stays_in_w3_with_message():
    svc, tray, _, _, gateway = make()
    svc.start()
    tray.place(["AGUA"])
    ticks(svc)
    svc.confirm()
    gateway.fail_create = True
    with pytest.raises(TransitionError, match="código QR"):
        svc.pay()
    assert svc.snapshot()["screen"] == "W3"


def test_poll_errors_keep_waiting():
    svc, _, gateway = paying()
    gateway.fail_poll = True
    svc.tick()
    assert svc.snapshot()["screen"] == "QR"


def test_polls_at_most_once_per_second():
    svc, clock, gateway = paying()
    svc.tick()
    svc.tick()
    assert gateway.polls == 1
    clock.t = 1.0
    svc.tick()
    assert gateway.polls == 2


def test_qr_payload_only_while_paying():
    svc, _, _, _, _ = make()
    assert svc.snapshot()["qr_payload"] is None


def test_rescan_clears_detection_and_reads_the_tray_again():
    svc, tray, _, _, _ = make()
    svc.start()
    tray.place(["AGUA"], hidden=["CHOCO"])
    ticks(svc)
    assert svc.snapshot()["alert"] == "Revise su bandeja"

    tray.place(["AGUA", "CHOCO"])  # el cliente acomoda la bandeja
    svc.rescan()
    snap = svc.snapshot()
    assert snap["screen"] == "W2"
    assert snap["lines"] == []
    assert snap["alert"] is None
    ticks(svc)
    assert svc.snapshot()["item_count"] == 2
    assert svc.snapshot()["weight"]["ok"] is True


def test_rescan_only_while_scanning():
    svc, _, _, _, _ = make()
    with pytest.raises(TransitionError):
        svc.rescan()


def test_rescan_is_counted_in_the_session():
    svc, tray, _, clock, gateway = make()
    svc.start()
    svc.rescan()
    tray.place(["AGUA"])
    ticks(svc)
    clock.t = 4.0
    svc.confirm()
    svc.pay()
    gateway.paid = True
    svc.tick()
    assert svc.sessions.sessions[0]["rescans"] == 1


def test_rescan_opens_a_visible_window_that_blocks_confirm():
    svc, tray, _, clock, _ = make()
    svc.start()
    tray.place(["AGUA"])
    ticks(svc)
    svc.rescan()
    assert svc.snapshot()["rescan_left"] == 4.0
    ticks(svc)
    assert svc.snapshot()["item_count"] == 1  # se ve cómo vuelve a aparecer
    with pytest.raises(TransitionError, match="Espera"):
        svc.confirm()
    clock.t = 1.5
    assert svc.snapshot()["rescan_left"] == 2.5
    clock.t = 4.0
    assert svc.snapshot()["rescan_left"] == 0.0
    svc.confirm()
    assert svc.snapshot()["screen"] == "W3"


def test_no_rescan_window_by_default():
    svc, _, _, _, _ = make()
    assert svc.snapshot()["rescan_left"] == 0.0
