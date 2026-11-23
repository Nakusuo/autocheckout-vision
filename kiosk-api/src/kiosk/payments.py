import re
import ssl
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import httpx
import jwt

ISSUER = "autocaja-mock-gateway"
AUDIENCE = "autocaja-kiosk"
HTTP_TIMEOUT_S = 2.0


class PaymentError(Exception):
    pass


@dataclass(frozen=True)
class Charge:
    id: str
    qr_payload: str


@dataclass(frozen=True)
class PaymentEvent:
    charge_id: str
    amount_cents: int


class PaymentGateway(Protocol):
    def create_charge(self, amount_cents: int, reference: str) -> Charge: ...

    def poll(self, charge_id: str) -> str | None: ...

    def confirm(self, charge_id: str) -> None: ...


class JwtVerifier:
    """Valida la confirmación firmada RS256 de la pasarela y rechaza reenvíos (jti)."""

    def __init__(self, public_key_pem: bytes, wall: Callable[[], float] = time.time):
        self._key = public_key_pem
        self._wall = wall
        # jti → exp. Un token vencido ya lo rechaza jwt.decode, así que se puede olvidar:
        # el registro no crece sin límite en un quiosco encendido por semanas.
        self._seen: dict[str, float] = {}

    def verify(self, token: str) -> PaymentEvent:
        try:
            claims = jwt.decode(
                token,
                self._key,
                algorithms=["RS256"],
                audience=AUDIENCE,
                issuer=ISSUER,
                options={"require": ["exp", "iat", "iss", "aud", "jti"]},
            )
        except jwt.PyJWTError as e:
            raise PaymentError(f"Token de pago inválido: {e}") from e
        if claims.get("status") != "PAID":
            raise PaymentError("El pago no figura como realizado")
        now = self._wall()
        self._seen = {jti: exp for jti, exp in self._seen.items() if exp >= now}
        if claims["jti"] in self._seen:
            raise PaymentError("Token de pago reutilizado")
        self._seen[claims["jti"]] = float(claims["exp"])
        return PaymentEvent(str(claims["charge_id"]), int(claims["amount_cents"]))


def tls13_context(ca_file: Path | str | None = None) -> ssl.SSLContext:
    """Contexto TLS que exige 1.3. Sin `ca_file` confía en las CA del sistema (pasarela en la nube)."""
    ctx = ssl.create_default_context(cafile=str(ca_file) if ca_file else None)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_3
    return ctx


class HttpGateway:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        ca_file: Path | None = None,
        transport: httpx.BaseTransport | None = None,
    ):
        self._client = httpx.Client(
            base_url=base_url,
            headers={"X-API-Key": api_key},
            timeout=HTTP_TIMEOUT_S,
            verify=tls13_context(ca_file),
            transport=transport,
        )

    def _call(self, method: str, path: str, **kwargs) -> dict:
        try:
            response = self._client.request(method, path, **kwargs)
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, ValueError) as e:
            raise PaymentError(f"Error con la pasarela: {e}") from e

    def create_charge(self, amount_cents: int, reference: str) -> Charge:
        data = self._call(
            "POST", "/charges", json={"amount_cents": amount_cents, "reference": reference}
        )
        return Charge(data["charge_id"], data["qr_payload"])

    def poll(self, charge_id: str) -> str | None:
        return self._call("GET", f"/charges/{charge_id}").get("token")

    def confirm(self, charge_id: str) -> None:
        self._call("POST", f"/charges/{charge_id}/confirm")


# --- Yape vía Mercado Pago (Checkout API) -------------------------------------------------
#
# Flujo documentado por Mercado Pago Perú (developers/.../integration-configuration/yape):
#   1. POST /platforms/pci/yape/v1/payment?public_key=...  {phoneNumber, otp, requestId} → token
#   2. POST /v1/payments (Bearer access token, X-Idempotency-Key) con payment_method_id="yape"
#      → respuesta síncrona: status "approved" o "rejected" (+ status_detail).
# El cliente escribe su celular y el «código de aprobación» de su app Yape (válido ~2 min).
# El quiosco no necesita una URL pública (no hay webhook): la respuesta llega en la misma llamada.

MP_API = "https://api.mercadopago.com"
YAPE_TIMEOUT_S = 10.0
DEFAULT_PAYER_EMAIL = "cliente@autocaja.pe"


@dataclass(frozen=True)
class YapeResult:
    """Resultado de un cobro con Yape. `status_detail` explica el rechazo (códigos de MP)."""

    payment_id: str
    approved: bool
    status_detail: str
    amount_cents: int


class UnverifiedPayment(PaymentError):
    """Mercado Pago aprobó el cobro pero la consulta de verificación falló o no coincide.

    El cliente quizá ya pagó: no se debe reintentar, la caja revisa la operación `payment_id`."""

    def __init__(self, message: str, payment_id: str, amount_cents: int):
        super().__init__(message)
        self.payment_id = payment_id
        self.amount_cents = amount_cents


class YapeProvider(Protocol):
    """Cobra con Yape. Errores de red o de configuración lanzan `PaymentError`."""

    def charge(self, amount_cents: int, reference: str, phone: str, otp: str) -> YapeResult: ...


class MercadoPagoYape:
    """Cobra con Yape usando la Checkout API de Mercado Pago.

    `base_url` es la API real (https://api.mercadopago.com) o la pasarela simulada, que imita
    los mismos endpoints y números de prueba. Con TLS 1.3 obligatorio en ambos casos (RNF-04).

    Errores del cliente (código vencido, sin saldo…) vuelven como `YapeResult(approved=False)`;
    fallos de red o de configuración (credenciales inválidas) lanzan `PaymentError`.
    """

    def __init__(
        self,
        base_url: str,
        public_key: str,
        access_token: str,
        payer_email: str = DEFAULT_PAYER_EMAIL,
        ca_file: Path | None = None,
        transport: httpx.BaseTransport | None = None,
    ):
        self._public_key = public_key
        self._access_token = access_token
        self._payer_email = payer_email
        self._client = httpx.Client(
            base_url=base_url,
            timeout=YAPE_TIMEOUT_S,
            verify=tls13_context(ca_file),
            transport=transport,
        )

    def _send(self, method: str, path: str, **kwargs) -> httpx.Response:
        try:
            response = self._client.request(method, path, **kwargs)
        except httpx.HTTPError as e:
            raise PaymentError(f"Mercado Pago no disponible: {e}") from e
        if response.status_code >= 500 or response.status_code in (401, 403):
            raise PaymentError(f"Mercado Pago respondió {response.status_code}")
        return response

    @staticmethod
    def _json(response: httpx.Response) -> dict:
        try:
            data = response.json()
        except ValueError as e:
            raise PaymentError("Respuesta de Mercado Pago no es JSON") from e
        if not isinstance(data, dict):
            raise PaymentError("Respuesta de Mercado Pago inesperada")
        return data

    def _token(self, phone: str, otp: str) -> str | None:
        """Token de un solo uso. None si Yape rechaza el celular o el código."""
        response = self._send(
            "POST",
            "/platforms/pci/yape/v1/payment",
            params={"public_key": self._public_key},
            json={"phoneNumber": phone, "otp": otp, "requestId": str(uuid.uuid4())},
        )
        if response.is_client_error:
            return None
        token = self._json(response).get("id")
        if not isinstance(token, str) or not token:
            raise PaymentError("Mercado Pago no devolvió el token de Yape")
        return token

    def charge(self, amount_cents: int, reference: str, phone: str, otp: str) -> YapeResult:
        token = self._token(phone, otp)
        if token is None:
            return YapeResult("", False, "invalid_phone_or_otp", amount_cents)
        auth = {"Authorization": f"Bearer {self._access_token}"}
        response = self._send(
            "POST",
            "/v1/payments",
            headers={**auth, "X-Idempotency-Key": f"{reference}-{uuid.uuid4()}"},
            json={
                "token": token,
                "transaction_amount": amount_cents / 100,
                "installments": 1,
                "payment_method_id": "yape",
                "description": f"AutoCaja {reference}",
                "external_reference": reference,
                "payer": {"email": self._payer_email},
            },
        )
        data = self._json(response)
        if response.is_client_error:
            return YapeResult("", False, str(data.get("message", "bad_request")), amount_cents)
        payment_id = str(data.get("id", ""))
        status, detail = data.get("status"), str(data.get("status_detail", ""))
        if status != "approved":
            return YapeResult(payment_id, False, detail or str(status), amount_cents)
        self._confirm(payment_id, amount_cents, reference, auth)
        return YapeResult(payment_id, True, detail, amount_cents)

    def _confirm(self, payment_id: str, amount_cents: int, reference: str, auth: dict) -> None:
        """No basta con la primera respuesta: se vuelve a consultar el pago y se exige que esté
        aprobado, por el mismo monto y con la referencia de esta venta."""
        try:
            data = self._json(self._send("GET", f"/v1/payments/{payment_id}", headers=auth))
        except PaymentError as e:
            raise UnverifiedPayment(str(e), payment_id, amount_cents) from e
        amount = data.get("transaction_amount")
        if (
            data.get("status") != "approved"
            or not isinstance(amount, int | float)
            or round(amount * 100) != amount_cents
            or data.get("external_reference") != reference
        ):
            raise UnverifiedPayment(
                f"El pago {payment_id} no coincide con la venta {reference}",
                payment_id,
                amount_cents,
            )


YAPE_MESSAGES = {
    "invalid_phone_or_otp": "Celular o código de aprobación incorrecto o vencido. "
    "Genera un código nuevo en Yape",
    "cc_rejected_bad_filled_security_code": "Código de aprobación incorrecto o vencido. "
    "Genera un código nuevo en Yape",
    "cc_rejected_call_for_authorize": "Yape pidió autorizar el pago. Revisa tu app e intenta de nuevo",
    "cc_amount_rate_limit_exceeded": "Superaste el límite de tu Yape. Usa otro medio de pago",
    "cc_rejected_insufficient_amount": "Saldo insuficiente en Yape",
    "cc_rejected_max_attempts": "Demasiados intentos en Yape. Usa otro medio de pago",
    "cc_rejected_form_error": "Revisa el número de celular y el código",
}
YAPE_DEFAULT_MESSAGE = "Yape rechazó el pago. Intenta de nuevo o pide ayuda"


def yape_message(status_detail: str) -> str:
    """Texto para el cliente según el motivo de rechazo de Mercado Pago."""
    return YAPE_MESSAGES.get(status_detail, YAPE_DEFAULT_MESSAGE)


# --- QR propio de Yape/Plin + notificación de pago ----------------------------------------
#
# El comercio muestra su QR de Yape (estático, el de su app). Cuando un cliente paga, al celular
# del comercio llega una notificación («Juan Pérez te yapeó S/ 4.30»). La futura app Android la
# leerá (NotificationListenerService, o una app de automatización como MacroDroid) y mandará el
# texto a POST /api/pay/notification.
# FORMATO VERIFICADO (Yape, 2026-11-20, una notificación real): título «Confirmación de Pago» y
# texto «Alessandra Rod* te envió un pago por S/ 1.5. El cód. de seguridad es: 305». El monto
# puede venir sin el cero final. Plin y otras variantes de Yape siguen SIN verificar, por eso el
# intérprete solo exige un monto «S/ …» y toma el nombre y el código si los encuentra.

_AMOUNT = re.compile(r"S/\.?\s*(\d{1,5}(?:[.,]\d{1,2})?)", re.IGNORECASE)
_PAYER_BEFORE = re.compile(
    r"^\W*(?:yape\W+)?(?P<name>[^\n]+?)\s+te\s+(?:yape[oó]|envi[oó]|pag[oó]|pline[oó])",
    re.IGNORECASE | re.MULTILINE,  # el título («Confirmación de Pago») puede ir en otra línea
)
_SECURITY_CODE = re.compile(
    r"c[oó]d(?:igo|\.)?\s+de\s+seguridad(?:\s+es)?\s*:?\s*(?P<code>\d{3,6})", re.IGNORECASE
)
_PAYER_AFTER = re.compile(r"\bde\s+(?P<name>[^\n.!]+?)\s*[.!]?\s*$", re.IGNORECASE)


@dataclass(frozen=True)
class WalletNotice:
    """Lo que se entiende de una notificación de pago recibido."""

    amount_cents: int
    payer: str | None
    security_code: str | None = None


def parse_wallet_notification(text: str) -> WalletNotice | None:
    """«Juan Pérez te yapeó S/ 4.30» → WalletNotice(430, "Juan Pérez"). None sin monto.

    Con el formato real de Yape también se lee el código de seguridad de 3 dígitos."""
    text = text.strip()[:500]
    found = _AMOUNT.search(text)
    if found is None:
        return None
    amount = found.group(1).replace(",", ".")
    cents = round(float(amount) * 100)
    if cents <= 0:
        return None
    code = _SECURITY_CODE.search(text)
    rest = _SECURITY_CODE.sub("", text[found.end() :])  # «… cód. de seguridad» no es un nombre
    match = _PAYER_BEFORE.search(text) or _PAYER_AFTER.search(rest)
    payer = match.group("name").strip(" :¡!") if match else None
    return WalletNotice(cents, payer or None, code.group("code") if code else None)
