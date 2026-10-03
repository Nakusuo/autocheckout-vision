import os
import sys
from collections.abc import Mapping
from pathlib import Path

import uvicorn

from kiosk.app import create_app
from kiosk.catalog import Catalog
from kiosk.payments import HttpGateway, JwtVerifier
from kiosk.scale import SimulatedScale
from kiosk.service import KioskService
from kiosk.store import init_db, load_catalog
from kiosk.tray import Detector, ScaleFollowingDetector, SimulatedTray

REPO = Path(__file__).resolve().parents[3]


def build_detector(
    mode: str, catalog: Catalog, scale: SimulatedScale, env: Mapping[str, str]
) -> tuple[Detector, SimulatedTray | None]:
    if mode == "sim":
        tray = SimulatedTray(catalog, scale)
        return tray, tray
    if mode == "camera":
        model = env.get("KIOSK_MODEL")
        if not model:
            sys.exit("Falta KIOSK_MODEL (ruta al modelo .onnx) para el modo cámara")
        from kiosk.vision import CameraSource, YoloOnnxDetector  # requiere el extra `vision`

        source = CameraSource(int(env.get("KIOSK_CAMERA", "0")))
        yolo = YoloOnnxDetector.from_model(
            Path(model), source, imgsz=int(env.get("KIOSK_IMGSZ", "416"))
        )
        return ScaleFollowingDetector(yolo, catalog, scale), None
    sys.exit(f"KIOSK_MODE desconocido: {mode!r} (usa 'sim' o 'camera')")


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
    detector, tray = build_detector(os.environ.get("KIOSK_MODE", "sim"), catalog, scale, os.environ)
    gateway = HttpGateway(
        os.environ.get("GATEWAY_URL", "https://localhost:8443"), api_key, ca_file=keys / "ca.pem"
    )
    verifier = JwtVerifier((keys / "gateway_jwt_public.pem").read_bytes())
    service = KioskService(catalog, detector, scale, gateway, verifier)
    app = create_app(service, tray, scale) if tray is not None else create_app(service)
    uvicorn.run(app, host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
