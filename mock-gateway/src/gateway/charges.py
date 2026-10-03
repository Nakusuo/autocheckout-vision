import secrets
import time
import uuid
from dataclasses import dataclass

import jwt

ISSUER = "autocaja-mock-gateway"
AUDIENCE = "autocaja-kiosk"
TOKEN_TTL_S = 300


@dataclass
class Charge:
    id: str
    amount_cents: int
    reference: str
    status: str = "PENDING"


class ChargeStore:
    def __init__(self) -> None:
        self._charges: dict[str, Charge] = {}

    def create(self, amount_cents: int, reference: str) -> Charge:
        charge = Charge(secrets.token_urlsafe(12), amount_cents, reference)
        self._charges[charge.id] = charge
        return charge

    def get(self, charge_id: str) -> Charge | None:
        return self._charges.get(charge_id)

    def mark_paid(self, charge_id: str) -> Charge:
        charge = self._charges[charge_id]
        charge.status = "PAID"
        return charge


def sign_payment(charge: Charge, private_key_pem: bytes, now: float | None = None) -> str:
    issued = int(time.time() if now is None else now)
    claims = {
        "iss": ISSUER,
        "aud": AUDIENCE,
        "iat": issued,
        "exp": issued + TOKEN_TTL_S,
        "jti": str(uuid.uuid4()),
        "charge_id": charge.id,
        "amount_cents": charge.amount_cents,
        "status": charge.status,
    }
    return jwt.encode(claims, private_key_pem, algorithm="RS256")
