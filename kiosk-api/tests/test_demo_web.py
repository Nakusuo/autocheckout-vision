"""Demo web / app: cámara del navegador con recuadro guía, QR propio de Yape y notificación."""

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient
from payment_helpers import FakeGateway

from kiosk.app import create_app
from kiosk.catalog import Catalog, Product
from kiosk.checkout import TransitionError
from kiosk.payments import WalletNotice, parse_wallet_notification
from kiosk.recognizer import CropRecognizer, Gallery
from kiosk.service import KioskService

CATALOG = Catalog(
    [Product("CASINO-43", "Galletas Casino 43 g", 150, 46.0), Product("RITZ-20", "Ritz", 130, 22.0)]
)


class NoCamera:
    def detect(self) -> list[str]:
        return []


class Clock:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t


def make_service(**kwargs) -> KioskService:
    return KioskService(
        CATALOG,
        NoCamera(),
        None,
        FakeGateway(),
        None,
        Clock(),
        wallet_qr="/api/pay/wallet-qr",
        browser_camera=True,
        **kwargs,
    )


def to_payment(svc: KioskService, skus=("CASINO-43", "RITZ-20")) -> None:
    svc.start()
    for sku in skus:
        svc.add_product(sku)
    svc.tick()
    svc.confirm()
    svc.pay()


# --- Intérprete de notificaciones ----------------------------------------------------


@pytest.mark.parametrize(
    ("text", "notice"),
    [
        ("Juan Pérez te yapeó S/ 2.80", WalletNotice(280, "Juan Pérez")),
        ("Yape! Ana Torres te envió un pago por S/ 15.50", WalletNotice(1550, "Ana Torres")),
        ("¡Luis R. te yapeó S/4,30!", WalletNotice(430, "Luis R.")),
        ("Recibiste S/ 12 de María López", WalletNotice(1200, "María López")),
        ("Te yapearon S/. 3.5", WalletNotice(350, None)),
        # Notificación real de Yape (2026-11-20): título en otra línea y monto sin el cero final
        (
            (
                "Confirmación de Pago\nAlessandra Rod* te envió un pago por S/ 1.5. "
                "El cód. de seguridad es: 305"
            ),
            WalletNotice(150, "Alessandra Rod*", "305"),
        ),
        (
            "Recibiste S/ 2 de Ana. Código de seguridad: 123",
            WalletNotice(200, "Ana", "123"),
        ),
    ],
)
def test_parses_amount_and_payer(text, notice):
    assert parse_wallet_notification(text) == notice


@pytest.mark.parametrize("text", ["Hola", "Te yapearon", "S/ 0.00 recibido", ""])
def test_without_a_positive_amount_there_is_no_notice(text):
    assert parse_wallet_notification(text) is None


# --- Servicio --------------------------------------------------------------------------


def test_add_product_builds_the_cart_only_while_scanning():
    svc = make_service()
    with pytest.raises(TransitionError, match="no permitida"):
        svc.add_product("CASINO-43")
    svc.start()
    svc.add_product("CASINO-43")
    svc.add_product("CASINO-43")
    svc.tick()
    snap = svc.snapshot()
    assert [(line["sku"], line["quantity"]) for line in snap["lines"]] == [("CASINO-43", 2)]
    with pytest.raises(TransitionError, match="catálogo"):
        svc.add_product("NO-EXISTE")
    svc.remove("CASINO-43")
    svc.tick()
    assert svc.snapshot()["item_count"] == 1


def test_snapshot_announces_browser_camera_and_wallet_qr():
    snap = make_service().snapshot()
    assert snap["browser_camera"] is True
    assert snap["payment_method"] == "yape-qr"
    assert snap["wallet_qr"] == "/api/pay/wallet-qr"
    assert snap["receipt"] is None


def test_pay_with_wallet_qr_waits_without_a_gateway_charge():
    svc = make_service()
    to_payment(svc)
    snap = svc.snapshot()
    assert snap["screen"] == "QR"
    assert snap["qr_payload"] is None
    assert snap["total_cents"] == 280


def test_matching_notification_completes_the_sale_with_a_receipt():
    svc = make_service()
    to_payment(svc)
    result = svc.wallet_notification("Juan Pérez te yapeó S/ 2.80")
    assert result == {"matched": True, "receipt": "B001-00000001"}
    snap = svc.snapshot()
    assert snap["screen"] == "W4"
    assert snap["receipt"]["number"] == "B001-00000001"
    assert snap["receipt"]["payer"] == "Juan Pérez"
    assert snap["receipt"]["issued_at"]
    assert svc.pos.receipts[-1]["charge_id"] == "billetera-venta-1"


def test_wrong_amount_or_no_payment_waiting_is_ignored():
    svc = make_service()
    assert (
        svc.wallet_notification("Ana te yapeó S/ 2.80")["reason"]
        == "No hay un cobro esperando pago"
    )
    to_payment(svc)
    wrong = svc.wallet_notification("Ana te yapeó S/ 2.00")
    assert wrong == {
        "matched": False,
        "reason": "Monto distinto: llegó S/ 2.00, se espera S/ 2.80",
    }
    assert svc.wallet_notification("Promoción del día")["matched"] is False
    assert svc.snapshot()["screen"] == "QR"


def test_money_that_does_not_match_alerts_the_cashier():
    svc = make_service()
    svc.wallet_notification("Luis te envió un pago por S/ 9. El cód. de seguridad es: 777")
    to_payment(svc)
    svc.wallet_notification("Promoción del día")  # sin monto: no es dinero, no alerta
    svc.wallet_notification("Ana te yapeó S/ 2.00")
    reasons = [a["reason"] for a in svc.security_alerts if a["outcome"] == "pagada"]
    assert reasons == [
        (
            "Yape de Luis por S/ 9.00, cód. 777 sin compra que calce "
            "(no hay un cobro esperando pago): revisar"
        ),
        (
            "Yape de Ana por S/ 2.00 sin compra que calce "
            "(monto distinto: llegó S/ 2.00, se espera S/ 2.80): revisar"
        ),
    ]


def test_real_yape_notification_pays_and_the_sale_keeps_its_detail():
    svc = make_service()
    to_payment(svc, skus=("CASINO-43",))
    total = svc.snapshot()["total_cents"]
    text = (
        "Confirmación de Pago\nAlessandra Rod* te envió un pago por "
        f"S/ {total / 100:g}. El cód. de seguridad es: 305"
    )
    assert svc.wallet_notification(text)["matched"] is True
    sale = svc.pos.sales_today()["receipts"][0]
    assert sale["payer"] == "Alessandra Rod*"
    assert sale["method"] == "Yape (notificación)"
    assert sale["lines"] == [{"name": svc.catalog.get("CASINO-43").name, "quantity": 1}]


def test_cashier_can_approve_a_wallet_qr_payment_by_hand():
    svc = make_service()
    to_payment(svc)
    svc.accept_payment()
    assert svc.snapshot()["screen"] == "W4"
    assert svc.pos.receipts[-1]["charge_id"] == "caja-billetera-venta-1"
    assert svc.pos.sales_today()["receipts"][0]["method"] == "Aprobado en caja"
    with pytest.raises(TransitionError, match="pago pendiente"):
        svc.accept_payment()


def test_receipt_disappears_when_the_kiosk_returns_to_start():
    svc = make_service()
    to_payment(svc)
    svc.wallet_notification("Ana te yapeó S/ 2.80")
    svc._clock.t += 11
    svc.tick()
    snap = svc.snapshot()
    assert snap["screen"] == "W1"
    assert snap["receipt"] is None


def test_notification_needs_wallet_mode():
    svc = KioskService(CATALOG, NoCamera(), None, FakeGateway(), None)
    with pytest.raises(TransitionError, match="QR de Yape/Plin"):
        svc.wallet_notification("Ana te yapeó S/ 1.00")
    assert svc.snapshot()["payment_method"] == "qr"
    assert svc.snapshot()["browser_camera"] is False


# --- Reconocedor del recuadro guía -------------------------------------------------------


def fake_embed(images):
    v = np.array([im.reshape(-1, 3).mean(axis=0) + 1 for im in images], np.float32)
    return v / np.linalg.norm(v, axis=1, keepdims=True)


def solid(color, size=64) -> np.ndarray:
    return np.full((size, size, 3), color, np.uint8)


def recognizer(threshold=1.2, margin=None, **gallery_options) -> CropRecognizer:
    from kiosk.recognizer import fingerprints

    vectors, labels = [], []
    for sku, color in (("CASINO-43", (30, 30, 200)), ("RITZ-20", (200, 60, 20))):
        img = solid(color)
        vectors.append(fingerprints(fake_embed, img, np.ones(img.shape[:2], np.uint8)))
        labels.append(sku)
    gallery = Gallery(np.vstack(vectors), np.array(labels), np.arange(2), **gallery_options)
    return CropRecognizer(fake_embed, gallery, threshold, margin)


def jpeg(img: np.ndarray) -> bytes:
    return cv2.imencode(".jpg", img)[1].tobytes()


def test_crop_recognizer_returns_best_product_score_and_margin():
    found = recognizer().recognize(solid((30, 30, 200)))
    assert found.sku == "CASINO-43"
    assert found.score > 1.2
    assert found.margin > 0
    assert found.match is True


def test_crop_recognizer_needs_a_clear_margin_over_the_second():
    # Parecido de sobra, pero sin ventaja suficiente sobre el segundo: no cuenta.
    found = recognizer(threshold=0.0, margin=5.0).recognize(solid((30, 30, 200)))
    assert (found.sku, found.match) == ("CASINO-43", False)


def test_crop_recognizer_uses_the_values_measured_for_its_gallery():
    base = recognizer()._gallery
    base.threshold, base.margin = 1.3, 0.07
    measured = CropRecognizer(fake_embed, base)
    assert (measured.threshold, measured.margin) == (1.3, 0.07)
    assert CropRecognizer(fake_embed, base, 1.1, 0.0).threshold == 1.1  # lo que se pasa manda
    base.threshold = base.margin = None
    legacy = CropRecognizer(fake_embed, base)
    assert (legacy.threshold, legacy.margin) == (1.0, 0.0)  # galerías de antes del recuadro


def test_crop_recognizer_reads_jpeg_bytes_and_rejects_garbage():
    rec = recognizer()
    assert rec.recognize_bytes(jpeg(solid((200, 60, 20)))).sku == "RITZ-20"
    assert rec.recognize_bytes(b"no es imagen") is None
    assert rec.recognize_bytes(b"") is None
    assert rec.recognize_bytes(jpeg(solid((200, 60, 20), size=16))) is None  # muy chica
    assert rec.recognize_bytes(b"x" * 2_000_001) is None


def test_crop_recognizer_rejects_decompression_bombs():
    # PNG chico en bytes pero de 17,6 MP: se descarta por la cabecera, sin abrirlo.
    bomb = cv2.imencode(".png", np.zeros((4200, 4200), np.uint8))[1].tobytes()
    assert len(bomb) < 2_000_000
    assert recognizer().recognize_bytes(bomb) is None


def test_image_size_reads_png_and_jpeg_headers():
    from kiosk.recognizer import image_size

    img = solid((1, 2, 3), size=40)[:, :30]
    assert image_size(cv2.imencode(".png", img)[1].tobytes()) == (30, 40)
    assert image_size(jpeg(img)) == (30, 40)
    assert image_size(b"\xff\xd8\x00\x00") is None  # JPEG roto
    assert image_size(b"\xff\xd8") is None  # sin cuadro
    assert image_size(b"GIF89a") is None


def test_crop_recognizer_from_files(tmp_path, monkeypatch):
    import kiosk.recognizer as module

    recognizer()._gallery.save(tmp_path / "g.npz")
    monkeypatch.setattr(module.Embedder, "from_model", classmethod(lambda cls, p, s: fake_embed))
    rec = module.CropRecognizer.from_files(tmp_path / "g.npz", tmp_path / "e.onnx", threshold=1.0)
    assert rec.threshold == 1.0
    assert rec.recognize(solid((30, 30, 200))).sku == "CASINO-43"


# --- Endpoints -------------------------------------------------------------------------


@pytest.fixture
def qr_file(tmp_path):
    path = tmp_path / "yape-qr.png"
    cv2.imwrite(str(path), solid((255, 255, 255)))
    return path


def client(qr_file, **kwargs):
    svc = make_service()
    options = {
        "recognizer": recognizer(),
        "wallet_qr_file": qr_file,
        "simulate_wallet": True,
        "notifier_key": "clave-del-notificador-123",
    }
    options.update(kwargs)
    return svc, TestClient(create_app(svc, run_loop=False, **options))


def test_frame_endpoint_suggests_a_product_during_scanning(qr_file):
    svc, http = client(qr_file)
    headers = {"Content-Type": "image/jpeg"}
    assert (
        http.post(
            "/api/vision/frame", content=jpeg(solid((30, 30, 200))), headers=headers
        ).status_code
        == 409
    )
    svc.start()
    body = http.post(
        "/api/vision/frame", content=jpeg(solid((30, 30, 200))), headers=headers
    ).json()
    assert body["match"] is True
    assert (body["sku"], body["name"], body["price_cents"]) == (
        "CASINO-43",
        "Galletas Casino 43 g",
        150,
    )
    assert svc.snapshot()["item_count"] == 0  # sugerir no agrega


def test_frame_endpoint_low_similarity_is_no_match(qr_file):
    svc, http = client(qr_file, recognizer=recognizer(threshold=9.0))
    svc.start()
    body = http.post(
        "/api/vision/frame",
        content=jpeg(solid((30, 30, 200))),
        headers={"Content-Type": "image/jpeg"},
    ).json()
    assert (body["match"], body["sku"], body["name"]) == (False, None, None)
    assert body["score"] > 0
    assert "margin" in body


def test_frame_endpoint_validates_the_upload(qr_file):
    svc, http = client(qr_file)
    svc.start()
    assert (
        http.post(
            "/api/vision/frame", content=b"x", headers={"Content-Type": "text/plain"}
        ).status_code
        == 415
    )
    big = b"x" * 2_000_001
    assert (
        http.post(
            "/api/vision/frame", content=big, headers={"Content-Type": "image/jpeg"}
        ).status_code
        == 413
    )
    bad = http.post("/api/vision/frame", content=b"x", headers={"Content-Type": "image/png; q=1"})
    assert bad.status_code == 422


def test_cart_add_endpoint(qr_file):
    svc, http = client(qr_file)
    assert http.post("/api/cart/add", json={"sku": "CASINO-43"}).status_code == 409
    svc.start()
    assert http.post("/api/cart/add", json={"sku": "CASINO-43"}).status_code == 200
    assert http.post("/api/cart/add", json={"sku": "minúsculas"}).status_code == 422


def test_wallet_qr_image_is_served(qr_file):
    _, http = client(qr_file)
    r = http.get("/api/pay/wallet-qr")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"
    assert r.headers["cache-control"] == "no-store"


def test_simulated_notification_pays(qr_file):
    svc, http = client(qr_file)
    to_payment(svc)
    r = http.post("/sim/wallet-notification", json={"text": "Juan te yapeó S/ 2.80"})
    assert r.json()["matched"] is True
    assert svc.snapshot()["screen"] == "W4"
    assert svc.pos.receipts[-1]["charge_id"] == "sim-billetera-venta-1"  # se distingue de la real


def test_notifier_endpoint_requires_the_key(qr_file):
    svc, http = client(qr_file)
    to_payment(svc)
    body = {"text": "Juan te yapeó S/ 2.80"}
    assert http.post("/api/pay/notification", json=body).status_code == 401
    bad = {"Authorization": "Bearer otra-clave-cualquiera"}
    assert http.post("/api/pay/notification", json=body, headers=bad).status_code == 401
    good = {"Authorization": "Bearer clave-del-notificador-123"}
    assert http.post("/api/pay/notification", json=body, headers=good).json()["matched"] is True


def test_routes_are_absent_unless_configured(qr_file):
    svc = KioskService(CATALOG, NoCamera(), None, FakeGateway(), None)
    http = TestClient(create_app(svc, run_loop=False))
    assert http.post("/api/vision/frame", content=b"x").status_code in (404, 405)
    assert http.get("/api/pay/wallet-qr").status_code == 404
    assert http.post("/sim/wallet-notification", json={"text": "a"}).status_code in (404, 405)
    assert http.post("/api/pay/notification", json={"text": "a"}).status_code in (404, 405)


def test_notification_in_wrong_mode_is_409(qr_file):
    svc = KioskService(CATALOG, NoCamera(), None, FakeGateway(), None)
    http = TestClient(create_app(svc, run_loop=False, simulate_wallet=True))
    assert http.post("/sim/wallet-notification", json={"text": "S/ 1"}).status_code == 409


def test_frame_endpoint_logs_only_changes(qr_file, caplog):
    caplog.set_level("INFO", logger="kiosk.app")
    svc, http = client(qr_file)
    svc.start()
    headers = {"Content-Type": "image/jpeg"}
    for color in ((30, 30, 200), (30, 30, 200), (200, 60, 20)):
        http.post("/api/vision/frame", content=jpeg(solid(color)), headers=headers)
    lines = [r.getMessage() for r in caplog.records if r.getMessage().startswith("Recuadro")]
    assert [line.split(" (")[0] for line in lines] == ["Recuadro: CASINO-43", "Recuadro: RITZ-20"]
