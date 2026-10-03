import os
import ssl
import sys
from pathlib import Path

import uvicorn

from gateway.app import create_app

REPO = Path(__file__).resolve().parents[3]


def main() -> None:
    keys = REPO / "keys"
    api_key = os.environ.get("GATEWAY_API_KEY")
    if not api_key:
        sys.exit("Falta GATEWAY_API_KEY (ver .env.example)")
    if not (keys / "gateway_jwt_private.pem").exists():
        sys.exit("Faltan claves: ejecuta primero `python -m gateway.devkeys`")
    public_url = os.environ.get("GATEWAY_PUBLIC_URL", "https://localhost:8443")
    app = create_app((keys / "gateway_jwt_private.pem").read_bytes(), api_key, public_url)
    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=8443,
        ssl_certfile=str(keys / "server.pem"),
        ssl_keyfile=str(keys / "server-key.pem"),
    )
    config.load()
    config.ssl.minimum_version = ssl.TLSVersion.TLSv1_3
    uvicorn.Server(config).run()


if __name__ == "__main__":
    main()
