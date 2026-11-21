"""Imitación de la API de Yape de Mercado Pago (Checkout API), para demo y pruebas sin red.

Mismos endpoints y forma de respuesta que la documentación de Mercado Pago Perú:
- POST /platforms/pci/yape/v1/payment?public_key=...  {phoneNumber, otp, requestId} → token
- POST /v1/payments   (Bearer, X-Idempotency-Key)     → status approved | rejected
- GET  /v1/payments/{id}

Números de prueba (los de Mercado Pago; OTP 123456). Cualquier otro celular se aprueba, para que
en la demo se pueda escribir uno real. Esto es una SIMULACIÓN: no mueve dinero.
"""

import secrets
import threading
from dataclasses import dataclass, field

TEST_OTP = "123456"
# Celulares de prueba de Mercado Pago y el status_detail que devuelve cada uno.
TEST_PHONES = {
    "111111111": ("approved", "accredited"),
    "111111112": ("rejected", "cc_rejected_call_for_authorize"),
    "111111113": ("rejected", "cc_amount_rate_limit_exceeded"),
    "111111114": ("rejected", "cc_unsupported_unsupported"),
    "111111115": ("rejected", "cc_rejected_card_type_not_allowed"),
    "111111116": ("rejected", "cc_rejected_max_attempts"),
    "111111117": ("rejected", "cc_rejected_bad_filled_security_code"),
    "111111118": ("rejected", "cc_rejected_form_error"),
}
MAX_AMOUNT = 2000.0  # tope por operación de Yape (S/)


class YapeError(Exception):
    """Petición inválida (equivale a un 400 de Mercado Pago)."""


@dataclass
class YapeStore:
    """Tokens de un solo uso y pagos, en memoria y seguros entre hilos."""

    _tokens: dict[str, str] = field(default_factory=dict)  # token → celular
    _payments: dict[int, dict] = field(default_factory=dict)
    _by_key: dict[str, int] = field(default_factory=dict)  # idempotencia
    _next_id: int = 1_000_000_001
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def create_token(self, phone: str, otp: str) -> dict:
        if phone.startswith("1111111") and otp != TEST_OTP:
            raise YapeError("invalid otp")
        token = secrets.token_hex(16)
        with self._lock:
            self._tokens[token] = phone
        return {"id": token, "status": "active", "site_id": "MPE", "payment_method_id": "yape"}

    def create_payment(self, body: dict, idempotency_key: str) -> dict:
        with self._lock:
            if idempotency_key in self._by_key:
                return self._payments[self._by_key[idempotency_key]]
            phone = self._tokens.pop(body["token"], None)  # un token sirve una sola vez
            if phone is None:
                raise YapeError("invalid token")
            status, detail = TEST_PHONES.get(phone, ("approved", "accredited"))
            if body["transaction_amount"] > MAX_AMOUNT:
                status, detail = "rejected", "cc_amount_rate_limit_exceeded"
            payment = {
                "id": self._next_id,
                "status": status,
                "status_detail": detail,
                "transaction_amount": body["transaction_amount"],
                "currency_id": "PEN",
                "payment_method_id": "yape",
                "payment_type_id": "debit_card",
                "external_reference": body.get("external_reference"),
                "description": body.get("description"),
            }
            self._payments[self._next_id] = payment
            self._by_key[idempotency_key] = self._next_id
            self._next_id += 1
            return payment

    def get(self, payment_id: int) -> dict | None:
        with self._lock:
            return self._payments.get(payment_id)
