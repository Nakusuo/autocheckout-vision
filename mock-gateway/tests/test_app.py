from pathlib import Path

import jwt
import pytest
from fastapi.testclient import TestClient

from gateway.app import create_app
from gateway.charges import AUDIENCE, ISSUER
from gateway.devkeys import write_signing_keys

KEY = {"X-API-Key": "clave-de-prueba"}


@pytest.fixture(scope="module")
def keys(tmp_path_factory) -> tuple[bytes, bytes]:
    out: Path = tmp_path_factory.mktemp("keys")
    write_signing_keys(out)
    return (out / "gateway_jwt_private.pem").read_bytes(), (
        out / "gateway_jwt_public.pem"
    ).read_bytes()


@pytest.fixture
def client(keys) -> TestClient:
    return TestClient(create_app(keys[0], "clave-de-prueba", "https://localhost:8443"))


def new_charge(client: TestClient, amount: int = 530) -> dict:
    r = client.post("/charges", json={"amount_cents": amount, "reference": "venta-1"}, headers=KEY)
    assert r.status_code == 201
    return r.json()


def test_create_requires_api_key(client):
    body = {"amount_cents": 530, "reference": "venta-1"}
    assert client.post("/charges", json=body).status_code == 401
    assert client.post("/charges", json=body, headers={"X-API-Key": "mala"}).status_code == 401


def test_non_ascii_api_key_is_401(client):
    r = client.post("/charges", json={"amount_cents": 1, "reference": "x"}, headers=[(b"x-api-key", "clavé".encode("latin-1"))])
    assert r.status_code == 401


def test_create_returns_qr_payload(client):
    charge = new_charge(client)
    assert charge["status"] == "PENDING"
    assert charge["qr_payload"] == f"https://localhost:8443/pay/{charge['charge_id']}"


def test_amount_must_be_positive(client):
    r = client.post("/charges", json={"amount_cents": 0, "reference": "x"}, headers=KEY)
    assert r.status_code == 422


def test_pending_charge_has_no_token(client):
    charge = new_charge(client)
    r = client.get(f"/charges/{charge['charge_id']}", headers=KEY)
    assert r.json() == {"charge_id": charge["charge_id"], "status": "PENDING"}


def test_pay_page_shows_amount(client):
    charge = new_charge(client)
    page = client.get(f"/pay/{charge['charge_id']}")
    assert page.status_code == 200
    assert "S/ 5.30" in page.text


def test_confirm_then_poll_returns_signed_token(client, keys):
    charge = new_charge(client)
    assert client.post(f"/pay/{charge['charge_id']}/confirm").status_code == 200

    body = client.get(f"/charges/{charge['charge_id']}", headers=KEY).json()
    assert body["status"] == "PAID"
    claims = jwt.decode(
        body["token"], keys[1], algorithms=["RS256"], audience=AUDIENCE, issuer=ISSUER
    )
    assert claims["status"] == "PAID"
    assert claims["amount_cents"] == 530


def test_unknown_charge_is_404(client):
    assert client.get("/charges/nope", headers=KEY).status_code == 404
    assert client.get("/pay/nope").status_code == 404
