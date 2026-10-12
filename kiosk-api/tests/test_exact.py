"""Valores exactos, para matar a los mutantes que sobrevivían (mutmut, 2026-10-12).

Las demás pruebas revisan comportamientos; estas fijan lo que se ve y se guarda: el estado
completo que recibe la pantalla, la boleta, la fila de métricas y los mensajes de error.
"""

import pytest
from payment_helpers import PUBLIC_PEM, FakeGateway, sign

from kiosk.catalog import Catalog, Product
from kiosk.checkout import Checkout, State, TransitionError
from kiosk.fusion import Cart, CartLine, build_cart, check_weight
from kiosk.payments import JwtVerifier
from kiosk.pos import SimulatedPos
from kiosk.scale import SimulatedScale
from kiosk.service import KioskService
from kiosk.tray import SimulatedTray

CATALOG = Catalog([Product("AGUA", "Agua", 250, 651.0), Product("CHOCO", "Chocolate", 280, 33.0)])


class Clock:
    def __init__(self):
        self.t = 100.0

    def __call__(self):
        return self.t


def make(scale_on: bool = True):
    clock = Clock()
    scale = SimulatedScale(noise_g=0)
    tray = SimulatedTray(CATALOG, scale)
    gateway = FakeGateway()
    pos = SimulatedPos(now=lambda: "2026-10-12T10:00:00+00:00")
    svc = KioskService(
        CATALOG, tray, scale if scale_on else None, gateway, JwtVerifier(PUBLIC_PEM), clock, pos=pos
    )
    return svc, tray, clock, gateway, pos


def scan(svc, tray, skus):
    tray.place(skus)
    for _ in range(3):
        svc.tick()


# ---------- snapshot completo ----------


def test_snapshot_on_w1_is_exact():
    svc, _, clock, _, _ = make()
    clock.t = 103.46
    assert svc.snapshot() == {
        "state": "IDLE",
        "screen": "W1",
        "can_pay": False,
        "lines": [],
        "total_cents": 0,
        "item_count": 0,
        "weight": None,
        "weight_enabled": True,
        "camera": False,
        "alert": None,
        "seconds_in_state": 3.5,
        "help_pending": False,
        "qr_payload": None,
    }


def test_snapshot_while_scanning_is_exact():
    svc, tray, clock, _, _ = make()
    svc.start()
    scan(svc, tray, ["AGUA", "CHOCO", "CHOCO"])
    clock.t += 1.04
    assert svc.snapshot() == {
        "state": "SCANNING",
        "screen": "W2",
        "can_pay": False,
        "lines": [
            {"sku": "AGUA", "name": "Agua", "quantity": 1, "unit_price_cents": 250},
            {"sku": "CHOCO", "name": "Chocolate", "quantity": 2, "unit_price_cents": 280},
        ],
        "total_cents": 810,
        "item_count": 3,
        "weight": {"ok": True, "diff_g": 0.0},
        "weight_enabled": True,
        "camera": False,
        "alert": None,
        "seconds_in_state": 1.0,
        "help_pending": False,
        "qr_payload": None,
    }


def test_snapshot_paying_shows_qr_and_help():
    svc, tray, _, _, _ = make(scale_on=False)
    svc.start()
    scan(svc, tray, ["AGUA"])
    svc.confirm()
    svc.pay()
    svc.request_help()
    snap = svc.snapshot()
    assert (snap["screen"], snap["can_pay"], snap["weight"], snap["weight_enabled"]) == (
        "QR",
        False,
        None,
        False,
    )
    assert snap["qr_payload"] == "https://localhost:8443/pay/ch_1"
    assert snap["help_pending"] is True


# ---------- pago, boleta y métricas ----------


def test_paid_sale_writes_exact_receipt_and_session():
    svc, tray, clock, gateway, pos = make(scale_on=False)
    svc.start()
    started = clock.t
    scan(svc, tray, ["CHOCO", "AGUA"])
    svc.confirm()
    svc.pay()
    assert gateway.amounts == [530]
    gateway.paid = True
    clock.t = started + 12.34
    svc.tick()
    assert svc.snapshot()["screen"] == "W4"
    assert pos.receipts == [
        {
            "number": "B001-00000001",
            "issued_at": "2026-10-12T10:00:00+00:00",
            "reference": "venta-1",
            "charge_id": "ch_1",
            "lines": [
                {"sku": "AGUA", "name": "Agua", "quantity": 1, "unit_price_cents": 250},
                {"sku": "CHOCO", "name": "Chocolate", "quantity": 1, "unit_price_cents": 280},
            ],
            "total_cents": 530,
        }
    ]
    row = svc.sessions.sessions[-1]
    assert (row["outcome"], row["duration_s"], row["items"], row["total_cents"]) == (
        "paid",
        12.3,
        2,
        530,
    )
    assert row["weight_checked"] is False


def test_each_sale_gets_the_next_reference(monkeypatch):
    svc, tray, _, gateway, _ = make(scale_on=False)
    refs = []
    original = gateway.create_charge
    monkeypatch.setattr(
        gateway, "create_charge", lambda amount, ref: refs.append(ref) or original(amount, ref)
    )
    for _ in range(2):
        svc.start()
        scan(svc, tray, ["AGUA"])
        svc.confirm()
        svc.pay()
        svc.cancel()
    assert refs == ["venta-1", "venta-2"]


def test_first_poll_is_immediate_and_then_once_per_second():
    svc, tray, clock, gateway, _ = make(scale_on=False)
    svc.start()
    scan(svc, tray, ["AGUA"])
    svc.confirm()
    svc.pay()
    svc.tick()
    assert gateway.polls == 1
    clock.t += 1.0
    svc.tick()
    assert gateway.polls == 2


def test_payment_with_wrong_amount_or_charge_keeps_waiting(monkeypatch):
    svc, tray, _, gateway, pos = make(scale_on=False)
    svc.start()
    scan(svc, tray, ["AGUA"])
    svc.confirm()
    svc.pay()
    monkeypatch.setattr(gateway, "poll", lambda cid: sign(charge_id=cid, amount_cents=249))
    svc.tick()
    assert svc.snapshot()["screen"] == "QR" and pos.receipts == []


def test_gateway_down_on_pay_has_clear_message():
    svc, tray, _, gateway, _ = make(scale_on=False)
    gateway.fail_create = True
    svc.start()
    scan(svc, tray, ["AGUA"])
    svc.confirm()
    with pytest.raises(
        TransitionError, match=r"^No se pudo generar el código QR\. Intente de nuevo$"
    ):
        svc.pay()
    assert svc.snapshot()["screen"] == "W3"


# ---------- ayuda, quitar, cancelar ----------


def test_help_requests_have_increasing_ids_screen_and_time():
    svc, _, clock, _, _ = make()
    first = svc.request_help()
    clock.t = 107.0
    svc.start()
    second = svc.request_help()
    assert first == {"id": 1, "screen": "W1", "at": 100.0}
    assert second == {"id": 2, "screen": "W2", "at": 107.0}
    assert svc.sessions._current["help_requested"] is True


def test_remove_messages_and_counts():
    svc, tray, _, _, _ = make(scale_on=False)
    with pytest.raises(TransitionError, match=r"^Acción no permitida en el estado IDLE$"):
        svc.remove("AGUA")
    svc.start()
    scan(svc, tray, ["AGUA"])
    with pytest.raises(TransitionError, match=r"^Ese producto no está en la lista$"):
        svc.remove("CHOCO")
    svc.remove("AGUA")
    assert svc.snapshot()["item_count"] == 0
    assert svc.sessions._current["removals"] == 1


def test_cancel_clears_everything_and_records_it():
    svc, tray, _, _, _ = make(scale_on=False)
    svc.start()
    scan(svc, tray, ["AGUA"])
    svc.cancel()
    assert svc.snapshot()["item_count"] == 0
    assert svc.sessions.sessions[-1]["outcome"] == "cancelled"
    tray.place([])
    svc.start()
    for _ in range(3):
        svc.tick()
    assert svc.snapshot()["lines"] == []  # lo de la compra anterior no vuelve


def test_on_cart_receives_every_change():
    carts: list[Cart] = []
    clock = Clock()
    scale = SimulatedScale(noise_g=0)
    tray = SimulatedTray(CATALOG, scale)
    svc = KioskService(
        CATALOG, tray, scale, FakeGateway(), JwtVerifier(PUBLIC_PEM), clock, on_cart=carts.append
    )
    svc.start()
    scan(svc, tray, ["AGUA"])
    assert carts[0].item_count == 0
    assert carts[-1].item_count == 1


# ---------- balanza conectable (simulador) ----------


def test_set_scale_switches_weight_checks_only_on_w1():
    svc, tray, _, _, _ = make()
    scale = svc._scale
    svc.set_scale(None)
    assert svc.snapshot()["weight_enabled"] is False
    svc.start()
    scan(svc, tray, ["AGUA"])
    svc.confirm()
    assert svc.snapshot()["can_pay"] is True  # sin balanza, alcanza con la cámara
    with pytest.raises(TransitionError, match=r"^La balanza solo se cambia con el quiosco en W1$"):
        svc.set_scale(scale)
    svc.cancel()
    svc.set_scale(scale)
    assert svc.snapshot()["weight_enabled"] is True


def test_recalibrate_without_camera_message():
    svc, *_ = make()
    with pytest.raises(TransitionError, match=r"^Este modo no usa cámara$"):
        svc.recalibrate()


# ---------- máquina de estados y carrito ----------


def test_checkout_error_messages_are_exact():
    co = Checkout(require_weight=False)
    co.start()
    with pytest.raises(TransitionError, match=r"^Se necesitan de 1 a 3 productos reconocidos$"):
        co.confirm()
    one = build_cart(["AGUA"], CATALOG)
    co.update(one, None)
    co.confirm()
    assert co.state is State.CONFIRMING
    strict = Checkout(require_weight=True)
    strict.start()
    strict.update(one, check_weight(651.0, 700.0))
    strict.confirm()
    with pytest.raises(TransitionError, match=r"^Revise su bandeja$"):
        strict.pay()


def test_confirm_rejects_unknown_products_and_more_than_three():
    for skus in (["AGUA", "RARO"], ["CHOCO"] * 4):
        co = Checkout(require_weight=False)
        co.start()
        co.update(build_cart(skus, CATALOG), None)
        with pytest.raises(TransitionError):
            co.confirm()


def test_cancel_and_reset_clear_cart_and_weight():
    co = Checkout(require_weight=True)
    co.start()
    co.update(build_cart(["AGUA"], CATALOG), check_weight(651.0, 651.0))
    co.cancel()
    assert (co.state, co.cart, co.weight) == (State.IDLE, None, None)


def test_build_cart_is_exact():
    cart = build_cart(["CHOCO", "RARO", "AGUA", "CHOCO", "RARO"], CATALOG)
    assert cart == Cart(
        lines=(CartLine("AGUA", "Agua", 1, 250), CartLine("CHOCO", "Chocolate", 2, 280)),
        theoretical_weight_g=717.0,
        total_cents=810,
        unknown_skus=("RARO", "RARO"),
    )


def test_check_weight_rounds_the_difference():
    assert check_weight(100.0, 105.04) == check_weight(100.0, 104.96)
    assert check_weight(100.0, 105.04).diff_g == 5.0
    assert check_weight(100.0, 94.9).ok is False
