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


# ---------- alerta a la caja ----------


def test_unknown_sends_one_alert_per_sale_and_tracks_the_outcome():
    svc = kiosk()
    see(svc, [UNKNOWN])
    see(svc, [])
    see(svc, [UNKNOWN])  # vuelve a aparecer: la misma alerta, una vez más
    see(svc, ["VIZZIO-19"])
    see(svc, [])
    assert svc.security_alerts == [
        {
            "id": 1,
            "reason": "Producto no reconocido frente a la cámara",
            "screen": "W2",
            "at": svc.security_alerts[0]["at"],
            "times": 2,
            "outcome": "en curso",
        }
    ]
    svc.confirm()
    svc.pay()
    svc._gateway.paid = True
    svc.tick()
    assert svc.security_alerts[0]["outcome"] == "pagada"


def test_alert_on_cancel_and_next_sale_gets_a_new_one():
    svc = kiosk()
    see(svc, [UNKNOWN])
    svc.cancel()
    assert svc.security_alerts[0]["outcome"] == "cancelada"
    svc.start()
    see(svc, ["OTRA-COSA"])
    assert [a["id"] for a in svc.security_alerts] == [1, 2]


def test_alert_in_w3_records_the_screen():
    svc = kiosk()
    see(svc, ["VIZZIO-19"])
    see(svc, [])
    svc.confirm()
    see(svc, [UNKNOWN])
    assert svc.security_alerts[0]["screen"] == "W3"


def test_no_alert_for_known_products():
    svc = kiosk()
    see(svc, ["VIZZIO-19"])
    assert svc.security_alerts == []


def test_alert_closes_when_the_kiosk_fails():
    svc = kiosk()
    see(svc, [UNKNOWN])
    svc.tick(RuntimeError("cámara"))
    assert svc.security_alerts[0]["outcome"] == "quiosco fuera de servicio"


def test_api_lists_and_resolves_alerts():
    from fastapi.testclient import TestClient

    from kiosk.app import create_app

    svc = kiosk()
    see(svc, [UNKNOWN])
    client = TestClient(create_app(svc, run_loop=False))
    assert [a["id"] for a in client.get("/api/alerts").json()] == [1]
    assert client.delete("/api/alerts/1").json() == []
    assert client.delete("/api/alerts/1").status_code == 404


# ---------- revisión (2026-10-13) ----------


def test_resolved_alert_comes_back_if_it_happens_again_in_the_same_sale():
    svc = kiosk()
    see(svc, [UNKNOWN])
    see(svc, [])
    assert svc.resolve_alert(1)
    see(svc, [UNKNOWN])
    assert [a["id"] for a in svc.security_alerts] == [2]


def test_hand_covering_a_product_may_count_it_twice_never_zero():
    # Ante la duda se prefiere contar de más (se ve en la lista y el cliente lo quita con «−»)
    # que de menos: dar por presente lo tapado permitía cambiar un producto por otro sin cobrar.
    svc = kiosk()
    see(svc, ["VIZZIO-19"])
    see(svc, [UNKNOWN])  # la mano tapa el producto
    see(svc, ["VIZZIO-19"])  # ¿el mismo u otro? no se sabe: se cuenta
    see(svc, [])
    assert svc.snapshot()["item_count"] == 2
    svc.remove("VIZZIO-19")
    assert svc.snapshot()["item_count"] == 1


def test_product_taken_away_while_something_unknown_stays_leaves_the_view():
    svc = kiosk()
    see(svc, ["VIZZIO-19"])
    see(svc, [UNKNOWN])
    see(svc, [])
    see(svc, ["VIZZIO-19"])  # otra unidad, pasada después
    assert svc.snapshot()["item_count"] == 2


def test_pending_alerts_and_help_are_capped():
    from kiosk import service

    svc = kiosk()
    for _ in range(service.MAX_PENDING + 5):
        svc.request_help()
        see(svc, [UNKNOWN])
        svc.cancel()
        svc.start()
    assert len(svc.help_requests) == service.MAX_PENDING
    assert len(svc.security_alerts) == service.MAX_PENDING
    assert svc.security_alerts[-1]["id"] == service.MAX_PENDING + 5


def test_flooding_alerts_never_hides_a_paid_one():
    from kiosk import service

    svc = kiosk()
    see(svc, [UNKNOWN])
    see(svc, [])
    see(svc, ["VIZZIO-19"])
    see(svc, [])
    svc.confirm()
    svc.pay()
    svc._gateway.paid = True
    svc.tick()
    assert svc.security_alerts[0]["outcome"] == "pagada"
    svc.tick()  # W4
    svc._clock = lambda: 1e9  # pasa el tiempo: vuelve a W1
    svc.tick()
    for _ in range(service.MAX_PENDING + 10):  # intento de tapar la alerta con compras canceladas
        svc.start()
        see(svc, [UNKNOWN])
        svc.cancel()
    assert svc.security_alerts[0]["id"] == 1
    assert len(svc.security_alerts) == service.MAX_PENDING
