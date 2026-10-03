import os
import sys
from pathlib import Path

import uvicorn

from kiosk.app import create_app
from kiosk.payments import HttpGateway, JwtVerifier
from kiosk.scale import SimulatedScale
from kiosk.service import KioskService
from kiosk.store import init_db, load_catalog
from kiosk.tray import SimulatedTray

REPO = Path(__file__).resolve().parents[3]


def main() -> None:
    keys = REPO / "keys"
    api_key = os.environ.get("GATEWAY_API_KEY")
    if not api_key:
        sys.exit("Falta GATEWAY_API_KEY (ver .env.example)")
    if not (keys / "gateway_jwt_public.pem").exists() or not (keys / "ca.pem").exists():
        sys.exit("Faltan claves: ejecuta primero `python -m gateway.devkeys` en mock-gateway")

    db = REPO / "kiosk-api" / "kiosk.db"
    init_db(db, REPO / "catalog" / "products.csv")
    catalog = load_catalog(db)
    scale = SimulatedScale()
    tray = SimulatedTray(catalog, scale)
    gateway = HttpGateway(
        os.environ.get("GATEWAY_URL", "https://localhost:8443"), api_key, ca_file=keys / "ca.pem"
    )
    verifier = JwtVerifier((keys / "gateway_jwt_public.pem").read_bytes())
    service = KioskService(catalog, tray, scale, gateway, verifier)
    uvicorn.run(create_app(service, tray, scale), host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
