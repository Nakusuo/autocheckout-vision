"""Arranque de la pasarela simulada.

Por defecto (desarrollo) escucha en 127.0.0.1:8443 con su propio TLS 1.3 y lee las claves de
<repo>/keys/. Las variables de entorno permiten correrla en un contenedor o en la nube:

- GATEWAY_HOST / GATEWAY_PORT (o PORT, que fijan los PaaS como Render): dónde escuchar.
- GATEWAY_TLS=off: sin TLS propio, porque lo termina el proxy del proveedor de nube.
- GATEWAY_KEYS_DIR: carpeta con gateway_jwt_private.pem (y server.pem/server-key.pem si hay TLS).
- GATEWAY_PUBLIC_URL (o RENDER_EXTERNAL_URL): URL pública que va dentro del QR.
"""

import os
import ssl
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import uvicorn

from gateway.app import create_app

REPO = Path(__file__).resolve().parents[3]
DEFAULT_PUBLIC_URL = "https://localhost:8443"


@dataclass(frozen=True)
class Settings:
    """Configuración de arranque leída del entorno."""

    api_key: str
    keys: Path
    host: str
    port: int
    tls: bool
    public_url: str


def load_settings(env: Mapping[str, str]) -> Settings:
    """Lee y valida la configuración; termina con un mensaje claro si algo falta o es inválido."""
    api_key = env.get("GATEWAY_API_KEY")
    if not api_key:
        sys.exit("Falta GATEWAY_API_KEY (ver .env.example)")
    tls_mode = env.get("GATEWAY_TLS", "on")
    if tls_mode not in ("on", "off"):
        sys.exit(f"GATEWAY_TLS desconocido: {tls_mode!r} (usa 'on' u 'off')")
    port_text = env.get("GATEWAY_PORT") or env.get("PORT") or "8443"
    if not port_text.isdigit() or not 0 < int(port_text) < 65536:
        sys.exit(f"Puerto inválido: {port_text!r}")
    keys = Path(env.get("GATEWAY_KEYS_DIR") or REPO / "keys")
    tls = tls_mode == "on"
    needed = ["gateway_jwt_private.pem"] + (["server.pem", "server-key.pem"] if tls else [])
    missing = [name for name in needed if not (keys / name).exists()]
    if missing:
        sys.exit(
            f"Faltan claves en {keys}: {', '.join(missing)}. "
            "Ejecuta primero `python -m gateway.devkeys`"
        )
    public_url = env.get("GATEWAY_PUBLIC_URL") or env.get("RENDER_EXTERNAL_URL") or DEFAULT_PUBLIC_URL
    return Settings(
        api_key=api_key,
        keys=keys,
        host=env.get("GATEWAY_HOST", "127.0.0.1"),
        port=int(port_text),
        tls=tls,
        public_url=public_url.rstrip("/"),
    )


def main() -> None:
    settings = load_settings(os.environ)
    app = create_app(
        (settings.keys / "gateway_jwt_private.pem").read_bytes(),
        settings.api_key,
        settings.public_url,
    )
    if not settings.tls:
        # En la nube el proxy del proveedor termina HTTPS; aquí llega HTTP desde ese proxy.
        uvicorn.run(app, host=settings.host, port=settings.port)
        return
    config = uvicorn.Config(
        app,
        host=settings.host,
        port=settings.port,
        ssl_certfile=str(settings.keys / "server.pem"),
        ssl_keyfile=str(settings.keys / "server-key.pem"),
    )
    config.load()
    config.ssl.minimum_version = ssl.TLSVersion.TLSv1_3
    uvicorn.Server(config).run()


if __name__ == "__main__":
    main()
