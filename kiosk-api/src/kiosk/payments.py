import ssl
import time
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


def tls13_context(ca_file: Path | str) -> ssl.SSLContext:
    ctx = ssl.create_default_context(cafile=str(ca_file))
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
            verify=tls13_context(ca_file) if ca_file else True,
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
        data = self._call("POST", "/charges", json={"amount_cents": amount_cents, "reference": reference})
        return Charge(data["charge_id"], data["qr_payload"])

    def poll(self, charge_id: str) -> str | None:
        return self._call("GET", f"/charges/{charge_id}").get("token")
