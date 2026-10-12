import ssl
import time

import certifi
import httpx
import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from payment_helpers import PUBLIC_PEM, sign

from kiosk.payments import (
    HttpGateway,
    JwtVerifier,
    PaymentError,
    PaymentEvent,
    tls13_context,
)


def test_valid_token_returns_event():
    event = JwtVerifier(PUBLIC_PEM).verify(sign(charge_id="ch_9", amount_cents=530))
    assert event == PaymentEvent("ch_9", 530)


def test_replayed_token_is_rejected():
    verifier = JwtVerifier(PUBLIC_PEM)
    token = sign()
    verifier.verify(token)
    with pytest.raises(PaymentError, match="reutilizado"):
        verifier.verify(token)


@pytest.mark.parametrize(
    "overrides",
    [
        {"aud": "otro"},
        {"iss": "otro"},
        {"exp": 1},
        {"status": "PENDING"},
    ],
)
def test_invalid_claims_are_rejected(overrides):
    with pytest.raises(PaymentError):
        JwtVerifier(PUBLIC_PEM).verify(sign(**overrides))


def test_token_signed_by_other_key_is_rejected():
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048).private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    with pytest.raises(PaymentError):
        JwtVerifier(PUBLIC_PEM).verify(sign(private_pem=other))


def test_hs256_algorithm_confusion_is_rejected():
    forged = jwt.encode({"status": "PAID"}, "secreto", algorithm="HS256")
    with pytest.raises(PaymentError):
        JwtVerifier(PUBLIC_PEM).verify(forged)


def test_missing_jti_is_rejected():
    token = sign()
    claims = jwt.decode(token, options={"verify_signature": False})
    del claims["jti"]
    from payment_helpers import PRIVATE_PEM

    with pytest.raises(PaymentError):
        JwtVerifier(PUBLIC_PEM).verify(jwt.encode(claims, PRIVATE_PEM, algorithm="RS256"))


def test_tls13_context_enforces_minimum_version():
    ctx = tls13_context(certifi.where())
    assert ctx.minimum_version == ssl.TLSVersion.TLSv1_3
    assert ctx.verify_mode == ssl.CERT_REQUIRED


def _gateway(handler) -> HttpGateway:
    return HttpGateway("https://gw.test", "k", transport=httpx.MockTransport(handler))


def test_http_gateway_create_and_poll():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["X-API-Key"] == "k"
        if request.method == "POST":
            return httpx.Response(
                201, json={"charge_id": "ch_1", "qr_payload": "q", "status": "PENDING"}
            )
        return httpx.Response(200, json={"charge_id": "ch_1", "status": "PAID", "token": "t"})

    gw = _gateway(handler)
    charge = gw.create_charge(530, "venta-1")
    assert (charge.id, charge.qr_payload) == ("ch_1", "q")
    assert gw.poll("ch_1") == "t"


def test_http_gateway_errors_become_payment_error():
    gw = _gateway(lambda request: httpx.Response(500))
    with pytest.raises(PaymentError):
        gw.create_charge(530, "venta-1")
    with pytest.raises(PaymentError):
        gw.poll("ch_1")


def test_replay_registry_forgets_expired_tokens():
    now = [time.time()]
    verifier = JwtVerifier(PUBLIC_PEM, wall=lambda: now[0])
    token = sign(jti="viejo")
    verifier.verify(token)
    with pytest.raises(PaymentError, match="reutilizado"):
        verifier.verify(token)  # dentro de su vigencia sigue rechazado
    now[0] += 301  # ya venció: no hace falta recordarlo
    verifier.verify(sign(jti="nuevo"))
    assert list(verifier._seen) == ["nuevo"]
