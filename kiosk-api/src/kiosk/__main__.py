import logging
import os
import sys
from collections.abc import Mapping
from logging.handlers import RotatingFileHandler
from pathlib import Path

import uvicorn

from kiosk.app import create_app
from kiosk.catalog import Catalog
from kiosk.metrics import SessionRecorder
from kiosk.payments import HttpGateway, JwtVerifier
from kiosk.pos import SimulatedPos
from kiosk.scale import SimulatedScale
from kiosk.service import KioskService
from kiosk.store import init_db, load_catalog
from kiosk.tray import Detector, SimulatedTray

REPO = Path(__file__).resolve().parents[3]
log = logging.getLogger("kiosk")


def build_detector(
    mode: str, catalog: Catalog, scale: SimulatedScale, env: Mapping[str, str]
) -> tuple[Detector, SimulatedTray | None]:
    if mode == "sim":
        tray = SimulatedTray(catalog, scale)
        return tray, tray
    if mode == "camera":
        gallery, model = env.get("KIOSK_GALLERY"), env.get("KIOSK_MODEL")
        from kiosk.vision import CameraSource, YoloOnnxDetector  # requiere el extra `vision`

        if gallery:
            from kiosk.recognizer import THRESHOLD, SimilarityDetector, parse_zone

            source = CameraSource(int(env.get("KIOSK_CAMERA", "0")))
            threshold = float(env.get("KIOSK_THRESHOLD", THRESHOLD))
            # KIOSK_ZONE=x0,y0,x1,y1 (fracciones): solo se reconoce lo que pasa por ese recuadro
            zone = parse_zone(env["KIOSK_ZONE"]) if env.get("KIOSK_ZONE") else None
            hands = env.get("KIOSK_HANDS", "on") != "off"
            detector = SimilarityDetector.from_files(
                Path(gallery), source, threshold=threshold, zone=zone, hands=hands
            )
            return detector, None
        if not model:
            sys.exit(
                "Modo cámara: falta KIOSK_GALLERY (galería de fotos, reconocimiento por parecido)"
                " o KIOSK_MODEL (YOLOv8 entrenado)"
            )
        source = CameraSource(int(env.get("KIOSK_CAMERA", "0")))
        yolo = YoloOnnxDetector.from_model(
            Path(model), source, imgsz=int(env.get("KIOSK_IMGSZ", "416"))
        )
        return yolo, None
    sys.exit(f"KIOSK_MODE desconocido: {mode!r} (usa 'sim' o 'camera')")


def scale_enabled(env: Mapping[str, str]) -> bool:
    """KIOSK_SCALE=off (por defecto): sin balanza, solo la cámara. sim: balanza simulada."""
    mode = env.get("KIOSK_SCALE", "off")
    if mode not in ("off", "sim"):
        sys.exit(f"KIOSK_SCALE desconocido: {mode!r} (usa 'off' o 'sim')")
    return mode == "sim"


def setup_logging(path: Path) -> None:
    """Consola y archivo con hora; el archivo rota a 1 MB y guarda 3 anteriores (~4 MB)."""
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    to_file = RotatingFileHandler(path, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    to_console = logging.StreamHandler()
    for handler in (to_file, to_console):
        handler.setFormatter(fmt)
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(to_console)
    root.addHandler(to_file)


def main() -> None:
    setup_logging(REPO / "kiosk-api" / "kiosk.log")
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
    try:
        detector, tray = build_detector(
            os.environ.get("KIOSK_MODE", "sim"), catalog, scale, os.environ
        )
    except (OSError, ValueError) as e:  # cámara que no abre, KIOSK_CAMERA/KIOSK_ZONE inválidos
        sys.exit(f"No se pudo preparar la cámara: {e}")
    gateway = HttpGateway(
        os.environ.get("GATEWAY_URL", "https://localhost:8443"), api_key, ca_file=keys / "ca.pem"
    )
    verifier = JwtVerifier((keys / "gateway_jwt_public.pem").read_bytes())
    pos = SimulatedPos(REPO / "kiosk-api" / "boletas.jsonl")
    sessions = SessionRecorder(REPO / "kiosk-api" / "sesiones.jsonl")
    use_scale = scale_enabled(os.environ)
    if not use_scale:
        log.info("Sin balanza (KIOSK_SCALE=off): se paga con lo que reconoce la cámara")
    # Con balanza simulada en modo cámara, la balanza pesa lo que se va escaneando:
    # la validación de peso (ON-02) NO protege nada en ese modo. Solo para demostrar la visión.
    follow = None
    if tray is None and use_scale:
        log.warning(
            "Modo cámara con balanza simulada: el peso sigue a la lista y no valida nada. "
            "Conecta una balanza real antes de usarlo con clientes."
        )
        follow = lambda cart: scale.set_load(cart.theoretical_weight_g)
    service = KioskService(
        catalog,
        detector,
        scale if use_scale else None,
        gateway,
        verifier,
        pos=pos,
        sessions=sessions,
        on_cart=follow,
    )
    if tray is not None:
        app = create_app(service, tray, scale)
    else:
        app = create_app(service, threaded_sensing=True)  # cámara: reconocer sin congelar
    uvicorn.run(app, host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
