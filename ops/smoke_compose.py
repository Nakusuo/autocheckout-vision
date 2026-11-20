"""Prueba de humo de AutoCaja en contenedores (docker compose, modo simulado).

Recorre una compra completa por el mismo camino que el navegador: interfaz en nginx
(http://localhost:5173), API detrás del proxy, pago en la pasarela por HTTPS (TLS 1.3)
verificando su certificado con la CA de desarrollo, y ticket en W4.

Uso (con `docker compose up -d` ya en marcha):
    docker compose cp mock-gateway:/app/keys/ca.pem /tmp/ca.pem
    python ops/smoke_compose.py --ca /tmp/ca.pem            # pago con QR
    python ops/smoke_compose.py --ca /tmp/ca.pem --pago yape # con KIOSK_PAYMENT=yape

Con `--pago yape` se usan los números de prueba de Mercado Pago: primero uno que rechaza
(«código incorrecto») y luego uno que aprueba.

Solo usa la biblioteca estándar para correr igual en el CI y en cualquier equipo.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import socket
import ssl
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from urllib.parse import urlparse

UI = "http://localhost:5173"
ORIGIN = {"Origin": UI}
PRODUCT = "RITZ-20"


def request(method: str, url: str, body: dict | None = None, **kwargs) -> tuple[int, bytes]:
    """Petición HTTP; devuelve (código, cuerpo) también cuando el código es de error."""
    data = json.dumps(body).encode() if body is not None else None
    headers = {**ORIGIN, **({"Content-Type": "application/json"} if data else {})}
    headers.update(kwargs.pop("headers", {}))
    # B310 (urlopen) revisado: solo URL http(s) fijas de este equipo, nunca datos externos
    req = urllib.request.Request(url, data=data, headers=headers, method=method)  # nosec B310
    try:
        with urllib.request.urlopen(req, timeout=5, **kwargs) as r:  # nosec B310
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


class SmokeError(Exception):
    """Un paso de la prueba de humo no dio lo esperado."""


def check(ok: bool, message: str) -> None:
    if not ok:
        raise SmokeError(message)


def api(method: str, path: str, body: dict | None = None) -> dict:
    status, raw = request(method, f"{UI}{path}", body)
    if status != 200:
        raise SmokeError(f"{method} {path} → {status}: {raw[:200]!r}")
    return json.loads(raw)


def wait_for(what: str, done: Callable[[dict], bool], timeout_s: float = 10) -> dict:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        state = api("GET", "/api/state")
        if done(state):
            return state
        time.sleep(0.3)
    raise SmokeError(f"No se llegó a «{what}» en {timeout_s} s; último estado: {state}")


def websocket_upgrades(url: str) -> bool:
    """Handshake mínimo de WebSocket a través de nginx: debe responder 101."""
    host = urlparse(url).hostname or "localhost"
    port = urlparse(url).port or 80
    key = base64.b64encode(os.urandom(16)).decode()
    handshake = (
        f"GET /ws HTTP/1.1\r\nHost: {host}:{port}\r\nUpgrade: websocket\r\n"
        f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\n"
        f"Sec-WebSocket-Version: 13\r\nOrigin: {UI}\r\n\r\n"
    )
    with socket.create_connection((host, port), timeout=5) as s:
        s.sendall(handshake.encode())
        return s.recv(1024).startswith(b"HTTP/1.1 101")


def step(text: str) -> None:
    print(f"✔ {text}")


def pay_with_qr(ca: str) -> None:
    state = wait_for("QR de pago", lambda s: bool(s["qr_payload"]))
    step(f"compra W1→W2→W3→QR (S/ {state['total_cents'] / 100:.2f})")
    pay_url = state["qr_payload"] + "/confirm"
    tls = ssl.create_default_context(cafile=ca)
    tls.minimum_version = ssl.TLSVersion.TLSv1_3
    status, raw = request("POST", pay_url, context=tls)
    check(status == 200 and "Pago realizado" in raw.decode(), f"pago → {status}")
    step("el «celular» paga en la pasarela por HTTPS con TLS 1.3 y certificado verificado")


def pay_with_yape() -> None:
    state = wait_for("pantalla de Yape", lambda s: s["screen"] == "QR")
    check(state.get("payment_method") == "yape", f"se esperaba Yape: {state.get('payment_method')}")
    step(f"compra W1→W2→W3→pago con Yape (S/ {state['total_cents'] / 100:.2f})")
    bad = api("POST", "/api/pay/yape", {"phone": "111111117", "otp": "123456"})
    check(bad["screen"] == "QR" and bool(bad["payment_error"]), f"rechazo → {bad}")
    step(f"Yape rechaza con mensaje para el cliente: «{bad['payment_error']}»")
    ok = api("POST", "/api/pay/yape", {"phone": "111111111", "otp": "123456"})
    check(ok["screen"] == "W4", f"pago aprobado → {ok['screen']}")
    step("Yape aprueba: token → cobro → confirmación (API de Mercado Pago imitada, TLS 1.3)")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ca", required=True, help="CA de desarrollo (ca.pem del volumen)")
    parser.add_argument("--pago", choices=["qr", "yape"], default="qr", help="medio de pago")
    args = parser.parse_args(argv)

    for page in ("/", "/sim", "/caja"):
        status, raw = request("GET", f"{UI}{page}")
        check(status == 200 and b"<div id=\"root\"" in raw, f"{page} → {status}")
    step("nginx sirve la interfaz en /, /sim y /caja")

    status, _ = request("POST", f"{UI}/api/start", headers={"Origin": "http://malicioso.test"})
    check(status == 403, f"un origen ajeno debía dar 403 y dio {status}")
    step("la API rechaza otros orígenes (403)")

    check(websocket_upgrades(UI), "el WebSocket /ws no respondió 101")
    step("el WebSocket /ws pasa por el proxy")

    state = api("GET", "/api/state")
    if state["screen"] != "W1":
        api("POST", "/api/cancel")
        wait_for("W1", lambda s: s["screen"] == "W1")
    api("POST", "/api/start")
    api("POST", "/sim/scan", {"sku": PRODUCT})
    wait_for("producto en la lista", lambda s: s["item_count"] == 1)
    api("POST", "/api/confirm")
    api("POST", "/api/pay")
    if args.pago == "yape":
        pay_with_yape()
    else:
        pay_with_qr(args.ca)

    wait_for("ticket W4", lambda s: s["screen"] == "W4")
    sales = api("GET", "/api/sales")
    check(sales["count"] >= 1, str(sales))
    step(f"ticket W4 y boleta registrada (ventas de hoy: {sales['count']})")
    print("Prueba de humo OK")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SmokeError as e:
        sys.exit(f"✘ {e}")
