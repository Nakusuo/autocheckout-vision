import time
import uuid

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from kiosk.payments import AUDIENCE, ISSUER, Charge, PaymentError

_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
PRIVATE_PEM = _key.private_bytes(
    serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
)
PUBLIC_PEM = _key.public_key().public_bytes(
    serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
)


def sign(private_pem: bytes = PRIVATE_PEM, **overrides) -> str:
    now = int(time.time())
    claims = {
        "iss": ISSUER,
        "aud": AUDIENCE,
        "iat": now,
        "exp": now + 300,
        "jti": str(uuid.uuid4()),
        "charge_id": "ch_1",
        "amount_cents": 250,
        "status": "PAID",
    }
    claims.update(overrides)
    return jwt.encode(claims, private_pem, algorithm="RS256")


class FakeGateway:
    """Pasarela falsa para las pruebas: cobra, y entrega un token firmado cuando `paid`."""

    def __init__(self) -> None:
        self.paid = False
        self.fail_create = False
        self.fail_poll = False
        self.paid_amount: int | None = None
        self.amounts: list[int] = []
        self.polls = 0

    def create_charge(self, amount_cents: int, reference: str) -> Charge:
        if self.fail_create:
            raise PaymentError("pasarela caída")
        self.amounts.append(amount_cents)
        return Charge("ch_1", "https://localhost:8443/pay/ch_1")

    def poll(self, charge_id: str) -> str | None:
        self.polls += 1
        if self.fail_poll:
            raise PaymentError("pasarela caída")
        if not self.paid:
            return None
        amount = self.paid_amount if self.paid_amount is not None else self.amounts[-1]
        return sign(charge_id=charge_id, amount_cents=amount)
