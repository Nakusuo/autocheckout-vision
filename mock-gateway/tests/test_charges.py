from pathlib import Path

import jwt
import pytest

from gateway.charges import AUDIENCE, ISSUER, ChargeStore, sign_payment
from gateway.devkeys import write_signing_keys


@pytest.fixture(scope="module")
def keys(tmp_path_factory) -> tuple[bytes, bytes]:
    out: Path = tmp_path_factory.mktemp("keys")
    write_signing_keys(out)
    return (out / "gateway_jwt_private.pem").read_bytes(), (
        out / "gateway_jwt_public.pem"
    ).read_bytes()


def test_store_create_and_mark_paid():
    store = ChargeStore()
    charge = store.create(530, "venta-1")
    assert store.get(charge.id).status == "PENDING"
    store.mark_paid(charge.id)
    assert store.get(charge.id).status == "PAID"


def test_mark_paid_unknown_raises():
    with pytest.raises(KeyError):
        ChargeStore().mark_paid("nope")


def test_sign_payment_claims(keys):
    private, public = keys
    charge = ChargeStore().create(530, "venta-1")
    token = sign_payment(charge, private, now=1_000_000.0)

    claims = jwt.decode(
        token,
        public,
        algorithms=["RS256"],
        audience=AUDIENCE,
        issuer=ISSUER,
        options={"verify_exp": False},
    )
    assert claims["charge_id"] == charge.id
    assert claims["amount_cents"] == 530
    assert claims["status"] == "PENDING"
    assert claims["exp"] - claims["iat"] == 300
    assert claims["jti"]
