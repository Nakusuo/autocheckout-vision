"""Desconocidos de la cámara (informe del equipo, 2026-10-13).

Un desconocido pasajero (una mano, un producto girado) no puede quedar guardado en la compra:
bloqueaba CONFIRMAR para siempre sin aparecer en la lista. Pero mientras está a la vista sí
bloquea: dos productos juntos devuelven DESCONOCIDO y no deben salir gratis.
"""

import pytest
from payment_helpers import PUBLIC_PEM, FakeGateway

from kiosk.catalog import Catalog, Product
from kiosk.checkout import TransitionError
from kiosk.payments import JwtVerifier
from kiosk.recognizer import UNKNOWN
from kiosk.service import KioskService, Reading

CATALOG = Catalog([Product("VIZZIO-19", "Vizzio 19 g", 300, 19.0)])


class Camera:
    def detect(self) -> list[str]:  # el servicio recibe las lecturas por tick(reading)
        return []

    def recalibrate(self) -> None:
        pass


def kiosk() -> KioskService:
    svc = KioskService(CATALOG, Camera(), None, FakeGateway(), JwtVerifier(PUBLIC_PEM))
    svc.start()
    return svc


def see(svc: KioskService, skus: list[str], frames: int = 3) -> None:
    for _ in range(frames):
        svc.tick(Reading(skus, None))


def test_passing_unknown_then_product_lets_you_confirm():
    svc = kiosk()
    see(svc, [UNKNOWN])
    assert svc.snapshot()["alert"] == "Hay un producto que no reconocemos"
    see(svc, ["VIZZIO-19"])
    see(svc, [])
    snap = svc.snapshot()
    assert [line["sku"] for line in snap["lines"]] == ["VIZZIO-19"]
    assert snap["total_cents"] == 300 and snap["alert"] is None
    svc.confirm()
    svc.pay()
    assert svc.snapshot()["screen"] == "QR"


def test_sku_outside_the_catalog_is_not_kept_either():
    svc = kiosk()
    see(svc, ["OTRA-COSA"])
    see(svc, [])
    see(svc, ["VIZZIO-19"])
    see(svc, [])
    svc.confirm()
    assert svc.snapshot()["screen"] == "W3"


def test_unknown_in_view_blocks_confirm_until_it_leaves():
    svc = kiosk()
    see(svc, ["VIZZIO-19"])
    see(svc, [UNKNOWN])  # p. ej. dos productos juntos frente a la cámara
    with pytest.raises(TransitionError):
        svc.confirm()
    see(svc, [])
    svc.confirm()
    assert svc.snapshot()["screen"] == "W3"


def test_unknown_appearing_in_w3_reopens_scanning():
    svc = kiosk()
    see(svc, ["VIZZIO-19"])
    see(svc, [])
    svc.confirm()
    see(svc, [UNKNOWN])
    assert svc.snapshot()["screen"] == "W2"
    assert svc.snapshot()["alert"] == "Hay un producto que no reconocemos"


def test_the_same_unknown_in_view_does_not_pile_up():
    svc = kiosk()
    see(svc, [UNKNOWN], frames=10)
    see(svc, [])
    assert svc.snapshot()["alert"] is None
    assert svc.snapshot()["item_count"] == 0
