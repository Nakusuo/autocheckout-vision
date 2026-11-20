import pytest
from fastapi.testclient import TestClient

from gateway.app import create_app
from gateway.devkeys import write_signing_keys
from gateway.yape import TEST_PHONES

AUTH = {"Authorization": "Bearer clave"}


@pytest.fixture(scope="module")
def private_key(tmp_path_factory) -> bytes:
    out = tmp_path_factory.mktemp("keys")
    write_signing_keys(out)
    return (out / "gateway_jwt_private.pem").read_bytes()


@pytest.fixture
def client(private_key) -> TestClient:
    return TestClient(create_app(private_key, "clave", "https://localhost:8443"))


def token(client: TestClient, phone: str = "111111111", otp: str = "123456") -> str:
    r = client.post(
        "/platforms/pci/yape/v1/payment?public_key=TEST-pk",
        json={"phoneNumber": phone, "otp": otp, "requestId": "r-1"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "active"
    return r.json()["id"]


def payment_body(tok: str, amount: float = 5.3) -> dict:
    return {
        "token": tok,
        "transaction_amount": amount,
        "installments": 1,
        "payment_method_id": "yape",
        "payer": {"email": "cliente@autocaja.pe"},
        "external_reference": "venta-1",
    }


def pay(client: TestClient, tok: str, key: str = "k-1", amount: float = 5.3):
    return client.post(
        "/v1/payments",
        json=payment_body(tok, amount),
        headers={**AUTH, "X-Idempotency-Key": key},
    )


def test_test_phone_approves_and_can_be_read_back(client):
    r = pay(client, token(client))
    assert r.status_code == 201
    body = r.json()
    assert (body["status"], body["status_detail"]) == ("approved", "accredited")
    assert body["transaction_amount"] == 5.3
    assert body["external_reference"] == "venta-1"
    again = client.get(f"/v1/payments/{body['id']}", headers=AUTH).json()
    assert again == body


@pytest.mark.parametrize("phone", [p for p, (s, _) in TEST_PHONES.items() if s == "rejected"])
def test_rejection_phones_return_their_detail(client, phone):
    body = pay(client, token(client, phone)).json()
    assert body["status"] == "rejected"
    assert body["status_detail"] == TEST_PHONES[phone][1]


def test_any_other_phone_is_approved_for_the_demo(client):
    assert pay(client, token(client, "987654321", "000000")).json()["status"] == "approved"


def test_test_phone_with_wrong_otp_is_rejected(client):
    r = client.post(
        "/platforms/pci/yape/v1/payment?public_key=TEST-pk",
        json={"phoneNumber": "111111111", "otp": "000000", "requestId": "r"},
    )
    assert r.status_code == 400


def test_token_is_single_use(client):
    tok = token(client)
    assert pay(client, tok, "k-1").status_code == 201
    assert pay(client, tok, "k-2").status_code == 400


def test_same_idempotency_key_returns_the_same_payment(client):
    tok = token(client)
    first = pay(client, tok, "k-1").json()
    assert pay(client, tok, "k-1").json() == first


def test_amount_over_yape_limit_is_rejected(client):
    body = pay(client, token(client), amount=2500).json()
    assert body["status_detail"] == "cc_amount_rate_limit_exceeded"


def test_payments_require_bearer_and_idempotency_key(client):
    tok = token(client)
    body = payment_body(tok)
    assert client.post("/v1/payments", json=body, headers={"X-Idempotency-Key": "k"}).status_code == 401
    bad = {"Authorization": "Bearer otra", "X-Idempotency-Key": "k"}
    assert client.post("/v1/payments", json=body, headers=bad).status_code == 401
    assert client.post("/v1/payments", json=body, headers=AUTH).status_code == 400
    assert client.get("/v1/payments/1", headers={"Authorization": "Basic x"}).status_code == 401


def test_unknown_payment_is_404(client):
    assert client.get("/v1/payments/42", headers=AUTH).status_code == 404


@pytest.mark.parametrize(
    "change",
    [
        {"installments": 2},
        {"payment_method_id": "visa"},
        {"transaction_amount": 0},
        {"payer": {"email": "no-es-correo"}},
    ],
)
def test_payment_body_is_validated(client, change):
    body = {**payment_body(token(client)), **change}
    r = client.post("/v1/payments", json=body, headers={**AUTH, "X-Idempotency-Key": "k"})
    assert r.status_code == 422


@pytest.mark.parametrize(
    "body",
    [
        {"phoneNumber": "12345", "otp": "123456", "requestId": "r"},
        {"phoneNumber": "111111111", "otp": "12", "requestId": "r"},
    ],
)
def test_token_body_is_validated(client, body):
    r = client.post("/platforms/pci/yape/v1/payment?public_key=pk", json=body)
    assert r.status_code == 422


def test_token_requires_public_key(client):
    r = client.post(
        "/platforms/pci/yape/v1/payment",
        json={"phoneNumber": "111111111", "otp": "123456", "requestId": "r"},
    )
    assert r.status_code == 422
