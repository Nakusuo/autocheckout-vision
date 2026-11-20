import logging
import os
import sys
from collections.abc import Mapping
from logging.handlers import RotatingFileHandler
from pathlib import Path
from urllib.parse import urlparse

import uvicorn

from kiosk.app import create_app
from kiosk.catalog import Catalog
from kiosk.metrics import SessionRecorder
from kiosk.payments import (
    DEFAULT_PAYER_EMAIL,
    MP_API,
    Charge,
    HttpGateway,
    JwtVerifier,
    MercadoPagoYape,
    PaymentError,
)
from kiosk.pos import SimulatedPos
from kiosk.scale import SimulatedScale
from kiosk.service import KioskService
from kiosk.store import init_db, load_catalog
from kiosk.tray import Detector, SimulatedTray

REPO = Path(__file__).resolve().parents[3]
log = logging.getLogger("kiosk")


class NoCamera:
    """KIOSK_MODE=web: la cámara está en el navegador (o la app) y manda el recuadro guía a
    /api/vision/frame; el quiosco no lee ninguna cámara propia."""

    def detect(self) -> list[str]:
        return []


def build_recognizer(env: Mapping[str, str]):
    """Reconocedor del recuadro guía para KIOSK_MODE=web (requiere el extra `vision`)."""
    from kiosk.recognizer import BOX_THRESHOLD, CropRecognizer

    gallery = env.get("KIOSK_GALLERY")
    if not gallery or not Path(gallery).exists():
        sys.exit("KIOSK_MODE=web: falta KIOSK_GALLERY (galería de fotos, ver docs/ml)")
    threshold = float(env.get("KIOSK_THRESHOLD") or BOX_THRESHOLD)
    return CropRecognizer.from_files(Path(gallery), threshold=threshold)


def build_detector(
    mode: str, catalog: Catalog, scale: SimulatedScale, env: Mapping[str, str]
) -> tuple[Detector, SimulatedTray | None]:
    if mode == "sim":
        tray = SimulatedTray(catalog, scale)
        return tray, tray
    if mode == "web":
        return NoCamera(), None
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
                Path(gallery),
                source,
                segmenter=background_segmenter(env),
                threshold=threshold,
                zone=zone,
                hands=hands,
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
    sys.exit(f"KIOSK_MODE desconocido: {mode!r} (usa 'sim', 'camera' o 'web')")


def background_segmenter(env: Mapping[str, str]) -> Path | None:
    """KIOSK_FONDO=fijo (por defecto): bandeja con cámara cenital. libre: cualquier fondo
    (pantalla vertical, producto en la mano); usa el modelo silueta.onnx (KIOSK_SEGMENTER)."""
    mode = env.get("KIOSK_FONDO", "fijo")
    if mode not in ("fijo", "libre"):
        sys.exit(f"KIOSK_FONDO desconocido: {mode!r} (usa 'fijo' o 'libre')")
    if mode == "fijo":
        return None
    path = Path(env.get("KIOSK_SEGMENTER") or REPO / "ml" / "data" / "models" / "silueta.onnx")
    if not path.exists():
        sys.exit(f"Fondo libre: falta el modelo {path} (ver docs/ml/reconocimiento.md)")
    return path


def scale_enabled(env: Mapping[str, str]) -> bool:
    """KIOSK_SCALE=off (por defecto): sin balanza, solo la cámara. sim: balanza simulada."""
    mode = env.get("KIOSK_SCALE", "off")
    if mode not in ("off", "sim"):
        sys.exit(f"KIOSK_SCALE desconocido: {mode!r} (usa 'off' o 'sim')")
    return mode == "sim"


def server_address(env: Mapping[str, str]) -> tuple[str, int]:
    """KIOSK_HOST/KIOSK_PORT. Por defecto 127.0.0.1:8000; en Docker se usa 0.0.0.0."""
    port = env.get("KIOSK_PORT", "8000")
    if not port.isdigit() or not 0 < int(port) < 65536:
        sys.exit(f"KIOSK_PORT inválido: {port!r}")
    return env.get("KIOSK_HOST", "127.0.0.1"), int(port)


def data_dir(env: Mapping[str, str]) -> Path:
    """KIOSK_DATA_DIR: dónde van kiosk.db, boletas, sesiones y el log (un volumen en Docker)."""
    path = Path(env.get("KIOSK_DATA_DIR") or REPO / "kiosk-api")
    path.mkdir(parents=True, exist_ok=True)
    return path


def gateway_ca(env: Mapping[str, str], keys: Path) -> Path | None:
    """GATEWAY_CA=system: la pasarela tiene un certificado público (nube) y se usan las CA del
    sistema. Si no, se confía solo en la CA de desarrollo (keys/ca.pem). TLS 1.3 en ambos casos."""
    mode = env.get("GATEWAY_CA", "dev")
    if mode not in ("dev", "system"):
        sys.exit(f"GATEWAY_CA desconocido: {mode!r} (usa 'dev' o 'system')")
    if mode == "system":
        return None
    if not (keys / "ca.pem").exists():
        sys.exit("Faltan claves: ejecuta primero `python -m gateway.devkeys` en mock-gateway")
    return keys / "ca.pem"


def payment_mode(env: Mapping[str, str]) -> str:
    """KIOSK_PAYMENT=qr (por defecto): QR de la pasarela simulada. yape: Yape vía Mercado Pago.
    yape-qr: el QR propio de Yape/Plin del comercio; el pago llega como notificación."""
    mode = env.get("KIOSK_PAYMENT", "qr")
    if mode not in ("qr", "yape", "yape-qr"):
        sys.exit(f"KIOSK_PAYMENT desconocido: {mode!r} (usa 'qr', 'yape' o 'yape-qr')")
    return mode


WALLET_QR_URL = "/api/pay/wallet-qr"


def wallet_settings(env: Mapping[str, str]) -> tuple[Path, bool, str | None]:
    """KIOSK_PAYMENT=yape-qr: (imagen del QR, simular notificaciones, clave del notificador).

    - KIOSK_YAPE_QR: imagen PNG/JPG del QR del comercio (la de «Mi QR» en Yape; fuera de git).
    - KIOSK_SIMULAR_PAGO=off apaga /sim/wallet-notification (encendido por defecto: demo web).
    - KIOSK_NOTIFIER_KEY (≥ 16 caracteres) habilita /api/pay/notification para la app Android.
    """
    path = Path(env.get("KIOSK_YAPE_QR") or REPO / "privado" / "yape-qr.png")
    if path.suffix.lower() not in (".png", ".jpg", ".jpeg") or not path.is_file():
        sys.exit(f"KIOSK_PAYMENT=yape-qr: falta la imagen de tu QR de Yape en {path} (PNG o JPG)")
    simulate = env.get("KIOSK_SIMULAR_PAGO", "on") != "off"
    key = env.get("KIOSK_NOTIFIER_KEY") or None
    if key is not None and len(key) < 16:
        sys.exit("KIOSK_NOTIFIER_KEY debe tener al menos 16 caracteres")
    return path, simulate, key


def build_yape(env: Mapping[str, str], keys: Path) -> MercadoPagoYape:
    """Cliente de Yape. MP_BASE_URL apunta a Mercado Pago (por defecto) o a la pasarela simulada,
    que imita sus endpoints; con la simulada se confía en la CA de desarrollo (ver gateway_ca)."""
    public_key, access_token = env.get("MP_PUBLIC_KEY"), env.get("MP_ACCESS_TOKEN")
    if not public_key or not access_token:
        sys.exit("Pago con Yape: faltan MP_PUBLIC_KEY y MP_ACCESS_TOKEN (credenciales de prueba)")
    base_url = env.get("MP_BASE_URL", MP_API)
    url = urlparse(base_url)
    if url.scheme != "https" or not url.hostname:
        sys.exit(f"MP_BASE_URL debe ser una URL https: {base_url!r}")
    ca_file = None if url.hostname == urlparse(MP_API).hostname else gateway_ca(env, keys)
    return MercadoPagoYape(
        base_url,
        public_key,
        access_token,
        payer_email=env.get("MP_PAYER_EMAIL", DEFAULT_PAYER_EMAIL),
        ca_file=ca_file,
    )


class NoQrGateway:
    """Con Yape no se generan QR: si algo lo pidiera, falla con un error claro."""

    def create_charge(self, amount_cents: int, reference: str) -> Charge:
        raise PaymentError("Este quiosco cobra con Yape, no con QR")

    def poll(self, charge_id: str) -> str | None:
        return None


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
    host, port = server_address(os.environ)
    data = data_dir(os.environ)
    setup_logging(data / "kiosk.log")
    keys = Path(os.environ.get("KIOSK_KEYS_DIR") or REPO / "keys")
    payment = payment_mode(os.environ)
    mode = os.environ.get("KIOSK_MODE", "sim")

    db = data / "kiosk.db"
    init_db(db, REPO / "catalog" / "products.csv")
    catalog = load_catalog(db)
    scale = SimulatedScale()
    try:
        detector, tray = build_detector(mode, catalog, scale, os.environ)
    except (OSError, ValueError) as e:  # cámara que no abre, KIOSK_CAMERA/KIOSK_ZONE inválidos
        sys.exit(f"No se pudo preparar la cámara: {e}")
    recognizer = build_recognizer(os.environ) if mode == "web" else None
    yape = build_yape(os.environ, keys) if payment == "yape" else None
    wallet = wallet_settings(os.environ) if payment == "yape-qr" else None
    if yape is not None or wallet is not None:
        if yape is not None:
            log.info("Cobro con Yape vía %s", os.environ.get("MP_BASE_URL", MP_API))
        else:
            log.info("Cobro con el QR propio de Yape/Plin; el pago llega como notificación")
        gateway: HttpGateway | NoQrGateway = NoQrGateway()
        verifier: JwtVerifier | None = None
    else:
        api_key = os.environ.get("GATEWAY_API_KEY")
        if not api_key:
            sys.exit("Falta GATEWAY_API_KEY (ver .env.example)")
        if not (keys / "gateway_jwt_public.pem").exists():
            sys.exit("Faltan claves: ejecuta primero `python -m gateway.devkeys` en mock-gateway")
        gateway = HttpGateway(
            os.environ.get("GATEWAY_URL", "https://localhost:8443"),
            api_key,
            ca_file=gateway_ca(os.environ, keys),
        )
        verifier = JwtVerifier((keys / "gateway_jwt_public.pem").read_bytes())
    pos = SimulatedPos(data / "boletas.jsonl")
    sessions = SessionRecorder(data / "sesiones.jsonl")
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
        yape=yape,
        wallet_qr=WALLET_QR_URL if wallet is not None else None,
        browser_camera=recognizer is not None,
    )
    wallet_file, simulate_wallet, notifier_key = wallet if wallet else (None, False, None)
    app = create_app(
        service,
        tray,
        scale if tray is not None else None,
        threaded_sensing=tray is None,  # cámara: reconocer sin congelar la pantalla
        recognizer=recognizer,
        wallet_qr_file=wallet_file,
        simulate_wallet=simulate_wallet,
        notifier_key=notifier_key,
    )
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
