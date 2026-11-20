"""Cobro con Yape vía Mercado Pago: cliente HTTP, flujo del servicio y endpoint."""

import json

import httpx
import pytest
from fastapi.testclient import TestClient
from payment_helpers import FakeGateway, FakeYape

from kiosk.app import create_app
from kiosk.catalog import Catalog, Product
from kiosk.checkout import TransitionError
from kiosk.payments import (
    YAPE_DEFAULT_MESSAGE,
    MercadoPagoYape,
    PaymentError,
    YapeResult,
    yape_message,
)
from kiosk.scale import SimulatedScale
from kiosk.service import MAX_YAPE_ATTEMPTS, PAYMENT_TIMEOUT_S, KioskService
from kiosk.tray import SimulatedTray

CATALOG = Catalog([Product("AGUA", "Agua", 250, 651.0), Product("CHOCO", "Chocolate", 280, 33.0)])


# --- Cliente de Mercado Pago -----------------------------------------------------------


class MpServer:
    """Imita las respuestas de Mercado Pago y guarda las peticiones recibidas."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.token_status = 200
        self.token_body: object = {"id": "tok_1", "status": "active"}
        self.payment_status = 201
        self.payment_body: object = {
            "id": 123,
            "status": "approved",
            "status_detail": "accredited",
            "transaction_amount": 5.3,
            "external_reference": "venta-1",
        }
        self.confirm_body: object | None = None  # None: igual que payment_body
        self.raise_on: str | None = None

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = request.url.path
        if self.raise_on and self.raise_on in path:
            raise httpx.ConnectError("sin red")
        if path == "/platforms/pci/yape/v1/payment":
            return httpx.Response(self.token_status, json=self.token_body)
        if request.method == "POST" and path == "/v1/payments":
            return httpx.Response(self.payment_status, json=self.payment_body)
        if request.method == "GET" and path == "/v1/payments/123":
            body = self.payment_body if self.confirm_body is None else self.confirm_body
            return httpx.Response(200, json=body)
        return httpx.Response(404, json={"message": "not found"})


def client(server: MpServer) -> MercadoPagoYape:
    return MercadoPagoYape(
        "https://api.test",
        "TEST-pk",
        "TEST-token",
        payer_email="cliente@test.pe",
        transport=httpx.MockTransport(server),
    )


def test_approved_payment_follows_the_documented_flow():
    server = MpServer()
    result = client(server).charge(530, "venta-1", "111111111", "123456")
    assert result == YapeResult("123", True, "accredited", 530)

    token_req, pay_req, confirm_req = server.requests
    assert token_req.url.params["public_key"] == "TEST-pk"
    token_body = json.loads(token_req.content)
    assert (token_body["phoneNumber"], token_body["otp"]) == ("111111111", "123456")
    assert token_body["requestId"]
    assert "authorization" not in token_req.headers  # el token se pide con la llave pública

    assert pay_req.headers["authorization"] == "Bearer TEST-token"
    assert pay_req.headers["x-idempotency-key"].startswith("venta-1-")
    assert json.loads(pay_req.content) == {
        "token": "tok_1",
        "transaction_amount": 5.3,
        "installments": 1,
        "payment_method_id": "yape",
        "description": "AutoCaja venta-1",
        "external_reference": "venta-1",
        "payer": {"email": "cliente@test.pe"},
    }
    assert confirm_req.method == "GET"
    assert confirm_req.headers["authorization"] == "Bearer TEST-token"


def test_each_attempt_uses_a_new_idempotency_key():
    server = MpServer()
    mp = client(server)
    mp.charge(530, "venta-1", "111111111", "123456")
    mp.charge(530, "venta-1", "111111111", "123456")
    keys = [r.headers["x-idempotency-key"] for r in server.requests if r.url.path == "/v1/payments"]
    assert len(set(keys)) == 2


def test_rejected_token_means_wrong_phone_or_code():
    server = MpServer()
    server.token_status = 400
    result = client(server).charge(530, "venta-1", "111111111", "000000")
    assert result == YapeResult("", False, "invalid_phone_or_otp", 530)
    assert len(server.requests) == 1  # no se intenta cobrar


def test_rejected_payment_returns_status_detail():
    server = MpServer()
    server.payment_body = {"id": 9, "status": "rejected", "status_detail": "cc_rejected_max_attempts"}
    result = client(server).charge(530, "venta-1", "111111116", "123456")
    assert result == YapeResult("9", False, "cc_rejected_max_attempts", 530)
    assert len(server.requests) == 2  # sin confirmación de un rechazo


def test_status_without_detail_is_reported():
    server = MpServer()
    server.payment_body = {"id": 9, "status": "in_process"}
    assert client(server).charge(530, "venta-1", "1", "1").status_detail == "in_process"


def test_bad_request_on_payment_is_a_rejection():
    server = MpServer()
    server.payment_status = 400
    server.payment_body = {"message": "invalid token"}
    result = client(server).charge(530, "venta-1", "111111111", "123456")
    assert result == YapeResult("", False, "invalid token", 530)


@pytest.mark.parametrize("status", [401, 403, 500, 503])
def test_server_or_credential_errors_raise(status):
    server = MpServer()
    server.payment_status = status
    with pytest.raises(PaymentError, match=str(status)):
        client(server).charge(530, "venta-1", "111111111", "123456")


def test_network_error_raises():
    server = MpServer()
    server.raise_on = "/platforms"
    with pytest.raises(PaymentError, match="no disponible"):
        client(server).charge(530, "venta-1", "111111111", "123456")


@pytest.mark.parametrize("body", [{}, {"id": ""}, {"id": 5}])
def test_token_without_id_raises(body):
    server = MpServer()
    server.token_body = body
    with pytest.raises(PaymentError, match="token"):
        client(server).charge(530, "venta-1", "111111111", "123456")


def test_non_json_or_unexpected_body_raises():
    server = MpServer()
    server.token_body = ["no", "es", "objeto"]
    with pytest.raises(PaymentError, match="inesperada"):
        client(server).charge(530, "venta-1", "111111111", "123456")

    def not_json(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"<html>")

    mp = MercadoPagoYape("https://api.test", "pk", "tk", transport=httpx.MockTransport(not_json))
    with pytest.raises(PaymentError, match="JSON"):
        mp.charge(530, "venta-1", "111111111", "123456")


@pytest.mark.parametrize(
    "confirm",
    [
        {"status": "pending", "transaction_amount": 5.3, "external_reference": "venta-1"},
        {"status": "approved", "transaction_amount": 9.99, "external_reference": "venta-1"},
        {"status": "approved", "transaction_amount": "5.3", "external_reference": "venta-1"},
        {"status": "approved", "transaction_amount": 5.3, "external_reference": "venta-2"},
    ],
)
def test_confirmation_must_match_the_sale(confirm):
    server = MpServer()
    server.confirm_body = confirm
    with pytest.raises(PaymentError, match="no coincide"):
        client(server).charge(530, "venta-1", "111111111", "123456")


def test_messages_for_the_customer():
    assert "código" in yape_message("invalid_phone_or_otp").lower()
    assert "límite" in yape_message("cc_amount_rate_limit_exceeded")
    assert yape_message("algo_nuevo") == YAPE_DEFAULT_MESSAGE


# --- Servicio del quiosco ------------------------------------------------------------


class FakeClock:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t


def make_service():
    clock = FakeClock()
    tray = SimulatedTray(CATALOG, SimulatedScale(noise_g=0))
    yape = FakeYape()
    gateway = FakeGateway()
    svc = KioskService(CATALOG, tray, None, gateway, None, clock, yape=yape)
    return svc, tray, clock, yape, gateway


def to_payment(svc: KioskService, tray: SimulatedTray) -> None:
    svc.start()
    tray.place(["AGUA"])
    for _ in range(3):
        svc.tick()
    svc.confirm()
    svc.pay()


def pay(svc: KioskService, phone: str = "111111111", otp: str = "123456") -> None:
    amount, reference = svc.begin_yape()
    svc.finish_yape(reference, amount, svc.charge_yape(amount, reference, phone, otp))


def test_pay_opens_yape_without_a_qr():
    svc, tray, _, _, gateway = make_service()
    to_payment(svc, tray)
    snap = svc.snapshot()
    assert snap["screen"] == "QR"
    assert snap["payment_method"] == "yape"
    assert snap["qr_payload"] is None
    assert (snap["payment_error"], snap["payment_processing"]) == (None, False)
    assert gateway.amounts == []  # la pasarela QR no se usa


def test_approved_yape_payment_ends_on_ticket_with_receipt():
    svc, tray, _, yape, _ = make_service()
    to_payment(svc, tray)
    pay(svc)
    assert yape.calls == [(250, "venta-1", "111111111", "123456")]
    assert svc.snapshot()["screen"] == "W4"
    receipt = svc.pos.receipts[-1]
    assert (receipt["charge_id"], receipt["total_cents"]) == ("pay_1", 250)


def test_rejection_stays_on_payment_with_a_message_and_allows_retry():
    svc, tray, _, yape, _ = make_service()
    to_payment(svc, tray)
    yape.results = [YapeResult("9", False, "cc_rejected_bad_filled_security_code", 250)]
    pay(svc)
    snap = svc.snapshot()
    assert snap["screen"] == "QR"
    assert "Código de aprobación" in snap["payment_error"]
    pay(svc)  # segundo intento aprobado
    assert svc.snapshot()["screen"] == "W4"


def test_too_many_rejections_ask_for_help():
    svc, tray, _, yape, _ = make_service()
    to_payment(svc, tray)
    yape.results = [YapeResult("9", False, "x", 250)] * MAX_YAPE_ATTEMPTS
    for _ in range(MAX_YAPE_ATTEMPTS):
        pay(svc)
    assert "pida ayuda en caja" in svc.snapshot()["payment_error"]
    with pytest.raises(TransitionError, match="Demasiados intentos"):
        svc.begin_yape()


def test_attempts_reset_when_leaving_the_payment_screen():
    svc, tray, _, yape, _ = make_service()
    to_payment(svc, tray)
    yape.results = [YapeResult("9", False, "x", 250)] * MAX_YAPE_ATTEMPTS
    for _ in range(MAX_YAPE_ATTEMPTS):
        pay(svc)
    svc.cancel()
    assert svc.snapshot()["payment_error"] is None
    to_payment(svc, tray)
    pay(svc)
    assert svc.snapshot()["screen"] == "W4"


def test_gateway_error_shows_a_connection_message():
    svc, tray, _, yape, _ = make_service()
    to_payment(svc, tray)
    yape.results = [PaymentError("caído")]
    pay(svc)
    snap = svc.snapshot()
    assert snap["screen"] == "QR"
    assert snap["payment_error"] == "No se pudo conectar con Yape. Intente de nuevo"
    assert snap["payment_processing"] is False


def test_cannot_cancel_or_time_out_while_processing():
    svc, tray, clock, _, _ = make_service()
    to_payment(svc, tray)
    amount, reference = svc.begin_yape()
    assert svc.snapshot()["payment_processing"] is True
    with pytest.raises(TransitionError, match="procesando"):
        svc.cancel()
    with pytest.raises(TransitionError, match="Ya se está procesando"):
        svc.begin_yape()
    clock.t += PAYMENT_TIMEOUT_S + 1
    svc.tick()
    assert svc.snapshot()["screen"] == "QR"  # no venció
    svc.finish_yape(reference, amount, YapeResult("p", True, "accredited", amount))
    assert svc.snapshot()["screen"] == "W4"


def test_approval_for_a_different_sale_raises_a_refund_alert():
    svc, tray, _, _, _ = make_service()
    to_payment(svc, tray)
    amount, _ = svc.begin_yape()
    svc.finish_yape("venta-99", amount, YapeResult("777", True, "accredited", amount))
    assert svc.snapshot()["screen"] == "QR"  # la compra en pantalla no se da por pagada
    alert = svc.security_alerts[-1]
    assert "777" in alert["reason"] and "devolver" in alert["reason"]
    assert alert["outcome"] == "pagada"


def test_approval_for_a_different_amount_raises_a_refund_alert():
    svc, tray, _, _, _ = make_service()
    to_payment(svc, tray)
    amount, reference = svc.begin_yape()
    svc.finish_yape(reference, amount, YapeResult("778", True, "accredited", amount + 1))
    assert svc.snapshot()["screen"] == "QR"
    assert "778" in svc.security_alerts[-1]["reason"]


def test_begin_yape_requires_yape_and_an_open_payment():
    svc, _, _, _, _ = make_service()
    with pytest.raises(TransitionError, match="No hay un cobro"):
        svc.begin_yape()
    tray = SimulatedTray(CATALOG, SimulatedScale(noise_g=0))
    plain = KioskService(CATALOG, tray, None, FakeGateway(), None)
    with pytest.raises(TransitionError, match="no cobra con Yape"):
        plain.begin_yape()
    assert isinstance(plain.charge_yape(1, "r", "1", "1"), PaymentError)
    assert plain.snapshot()["payment_method"] == "qr"


def test_qr_mode_without_verifier_never_polls():
    gateway = FakeGateway()
    tray = SimulatedTray(CATALOG, SimulatedScale(noise_g=0))
    svc = KioskService(CATALOG, tray, None, gateway, None, FakeClock())
    to_payment(svc, tray)
    gateway.paid = True
    svc.tick()
    assert gateway.polls == 0
    assert svc.snapshot()["screen"] == "QR"


# --- Endpoint /api/pay/yape ---------------------------------------------------------


def make_app():
    svc, tray, _, yape, _ = make_service()
    return svc, tray, yape, TestClient(create_app(svc, tray, run_loop=False))


def test_endpoint_pays_and_returns_the_ticket_state():
    svc, tray, yape, http = make_app()
    to_payment(svc, tray)
    r = http.post("/api/pay/yape", json={"phone": "111111111", "otp": "123456"})
    assert r.status_code == 200
    assert r.json()["screen"] == "W4"
    assert yape.calls[0][2:] == ("111111111", "123456")


def test_endpoint_returns_rejection_in_the_snapshot():
    svc, tray, yape, http = make_app()
    to_payment(svc, tray)
    yape.results = [YapeResult("9", False, "cc_amount_rate_limit_exceeded", 250)]
    body = http.post("/api/pay/yape", json={"phone": "111111113", "otp": "123456"}).json()
    assert body["screen"] == "QR"
    assert "límite" in body["payment_error"]


def test_endpoint_rejects_when_no_payment_is_open():
    _, _, _, http = make_app()
    r = http.post("/api/pay/yape", json={"phone": "111111111", "otp": "123456"})
    assert r.status_code == 409
    assert "No hay un cobro" in r.json()["detail"]


@pytest.mark.parametrize(
    "body",
    [
        {"phone": "12345678", "otp": "123456"},
        {"phone": "1234567890", "otp": "123456"},
        {"phone": "11111111a", "otp": "123456"},
        {"phone": "111111111", "otp": "12345"},
        {"phone": "111111111", "otp": "1234567"},
        {"phone": "111111111"},
    ],
)
def test_endpoint_validates_phone_and_code(body):
    svc, tray, yape, http = make_app()
    to_payment(svc, tray)
    assert http.post("/api/pay/yape", json=body).status_code == 422
    assert yape.calls == []
