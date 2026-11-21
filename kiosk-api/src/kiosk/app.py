import asyncio
import hmac
import logging
import time
from collections.abc import Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Protocol

from fastapi import Depends, FastAPI, Header, HTTPException, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field, StringConstraints
from starlette.responses import FileResponse, JSONResponse
from starlette.staticfiles import StaticFiles

from kiosk.checkout import State, TransitionError
from kiosk.scale import SimulatedScale
from kiosk.service import KioskService, Reading
from kiosk.tray import SimulatedTray

log = logging.getLogger(__name__)

TICK_S = 0.2
ALLOWED_ORIGINS = {"http://localhost:5173", "http://127.0.0.1:5173"}
# Cabeceras de la interfaz cuando la sirve la propia API (nube, sin nginx): igual que nginx.conf.
UI_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
    "Content-Security-Policy": (
        "default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; "
        "connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    ),
    "Permissions-Policy": "camera=(self), microphone=(), geolocation=()",
}


# Un SKU del catálogo: mayúsculas, dígitos, punto y guion (p. ej. KRPINA-3.03L).
Sku = Annotated[str, StringConstraints(min_length=1, max_length=32, pattern=r"^[A-Z0-9.-]+$")]


class TrayIn(BaseModel):
    skus: list[Sku] = Field(max_length=20)
    hidden: list[Sku] = Field(default=[], max_length=20)


class SkuIn(BaseModel):
    sku: Sku


class ScaleIn(BaseModel):
    enabled: bool


class YapeIn(BaseModel):
    """Celular (9 dígitos) y código de aprobación de Yape (6 dígitos). No se guardan ni se loguean."""

    phone: Annotated[str, StringConstraints(pattern=r"^\d{9}$")]
    otp: Annotated[str, StringConstraints(pattern=r"^\d{6}$")]


def notifier_token(authorization: str | None) -> str | None:
    """Clave de la cabecera Authorization, tolerante con lo que escriben las apps de automatización
    (MacroDroid): «Bearer x», «bearer  x», espacios o saltos de línea al pegar, o la clave sola."""
    value = (authorization or "").strip()
    if not value:
        return None
    scheme, _, rest = value.partition(" ")
    return rest.strip() if scheme.lower() == "bearer" else value


def notifier_problem(token: str | None, key: str) -> str:
    """Motivo del rechazo para el log. Nunca incluye la clave ni lo recibido."""
    if token is None:
        return "no llegó la cabecera Authorization"
    if token.startswith("KIOSK_NOTIFIER_KEY"):
        return "se pegó también «KIOSK_NOTIFIER_KEY=»: va solo lo que sigue al «=»"
    if len(token) != len(key):
        return f"la clave tiene {len(token)} caracteres y se esperaban {len(key)}"
    return "la clave tiene el largo correcto pero no coincide"


class NotificationIn(BaseModel):
    """Texto de la notificación de pago recibido (Yape/Plin) tal como la muestra el celular."""

    text: str = Field(min_length=1, max_length=500)
    # Alternativa a la cabecera Authorization: algunas apps de automatización (MacroDroid) no la
    # mandan bien. En el cuerpo no queda en el log de accesos, a diferencia de la URL.
    key: str | None = Field(default=None, max_length=200)


class FrameMatch(Protocol):
    """Resultado de un recuadro (kiosk.recognizer.BoxMatch)."""

    sku: str
    score: float
    margin: float
    match: bool


class FrameRecognizer(Protocol):
    """Reconocedor del recuadro guía (kiosk.recognizer.CropRecognizer, extra `vision`)."""

    def recognize_bytes(self, data: bytes) -> FrameMatch | None: ...


MAX_FRAME_BYTES = 2_000_000


class TrapIn(BaseModel):
    offset_g: float = Field(ge=-5000, le=5000)


def safe_tick(service: KioskService, reading: Reading | Exception | None = None) -> None:
    try:
        service.tick(reading) if reading is not None else service.tick()
    except Exception:
        log.exception("Error en tick; el bucle sigue")


def capture(service: KioskService) -> Reading | Exception:
    """Corre en un hilo: si falla, devuelve el error para que el bucle lo procese."""
    try:
        return service.read_sensors()
    except Exception as e:  # noqa: BLE001 - el bucle principal decide (fuera de servicio)
        return e


def create_app(
    service: KioskService,
    tray: SimulatedTray | None = None,
    scale: SimulatedScale | None = None,
    run_loop: bool = True,
    threaded_sensing: bool = False,
    recognizer: FrameRecognizer | None = None,
    wallet_qr_file: Path | None = None,
    simulate_wallet: bool = False,
    notifier_key: str | None = None,
    allowed_origins: set[str] | None = None,
    caja_key: str | None = None,
    ui_dir: Path | None = None,
) -> FastAPI:
    """threaded_sensing: la cámara se lee en otro hilo para que la pantalla y los botones no se
    congelen mientras se reconoce (~200 ms por cuadro); el estado solo cambia en este bucle.

    Demo web / app (cada parte se activa solo si se da):
    - `recognizer`: POST /api/vision/frame reconoce el recuadro guía que manda el navegador.
    - `wallet_qr_file`: GET /api/pay/wallet-qr sirve la imagen del QR de Yape/Plin del comercio.
    - `simulate_wallet`: POST /sim/wallet-notification simula la notificación de pago (demo).
    - `notifier_key`: POST /api/pay/notification para la futura app Android, con
      `Authorization: Bearer <clave>`; sin la clave correcta responde 401.

    En la nube:
    - `allowed_origins`: orígenes extra aceptados (p. ej. https://kiosco.ejemplo.pe).
    - `caja_key`: las rutas de la caja (ayudas, alertas, ventas, reactivar…) exigen la cabecera
      `X-Caja-Key`; sin ella responden 401. Sin `caja_key` quedan abiertas (quiosco local).
    - `ui_dir`: la API también sirve la interfaz compilada (/ y /ayuda), sin nginx.
    """
    origins = ALLOWED_ORIGINS | (allowed_origins or set())

    def origin_ok(origin: str | None, host: str | None) -> bool:
        """Sin Origin (curl, app Android) pasa; si no, uno de la lista o el propio sitio por https.

        «El propio sitio por https» (Origin == https://<Host>) es la misma página que sirve esta
        API, p. ej. en Cloud Run, cuya dirección no se conoce antes del primer despliegue. Por
        http no se acepta: un dominio ajeno que apunte a 127.0.0.1 (DNS rebinding) coincidiría."""
        return (
            origin is None
            or origin in origins
            or (host is not None and origin == f"https://{host}")
        )

    def require_caja(x_caja_key: str | None = Header(default=None)) -> None:
        """Dependencia de las rutas de la caja: compara la clave en tiempo constante."""
        if caja_key is None:
            return
        if x_caja_key is None or not hmac.compare_digest(x_caja_key.encode(), caja_key.encode()):
            raise HTTPException(status_code=401, detail="Clave de caja inválida")

    caja = [Depends(require_caja)]

    async def tick_loop() -> None:
        while True:
            started = time.monotonic()
            reading = None
            if threaded_sensing and service.wants_reading():
                reading = await asyncio.to_thread(capture, service)
            safe_tick(service, reading)
            await asyncio.sleep(max(0.0, TICK_S - (time.monotonic() - started)))

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        task = asyncio.create_task(tick_loop()) if run_loop else None
        yield
        if task:
            task.cancel()

    # Sin /docs ni /redoc: el quiosco no publica la descripción de su API.
    app = FastAPI(
        title="kiosk-api", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None
    )

    @app.middleware("http")
    async def check_origin(request: Request, call_next):
        if not origin_ok(request.headers.get("origin"), request.headers.get("host")):
            return JSONResponse({"detail": "Origen no permitido"}, status_code=403)
        response = await call_next(request)
        if ui_dir is not None:
            for name, value in UI_HEADERS.items():
                response.headers.setdefault(name, value)
        return response

    def act(action: Callable[[], None]) -> dict:
        try:
            action()
        except TransitionError as e:
            raise HTTPException(status_code=409, detail=str(e)) from e
        return service.snapshot()

    @app.get("/api/state")
    async def state() -> dict:
        return service.snapshot()

    @app.post("/api/start")
    async def start() -> dict:
        return act(service.start)

    @app.post("/api/confirm")
    async def confirm() -> dict:
        return act(service.confirm)

    @app.post("/api/cancel")
    async def cancel() -> dict:
        return act(service.cancel)

    @app.post("/api/remove")
    async def remove(body: SkuIn) -> dict:
        return act(lambda: service.remove(body.sku))

    @app.post("/api/correct")
    async def correct() -> dict:
        return act(service.correct)

    @app.post("/api/pay")
    async def pay() -> dict:
        return act(service.pay)

    @app.post("/api/pay/yape")
    async def pay_yape(body: YapeIn) -> dict:
        try:
            amount, reference = service.begin_yape()
        except TransitionError as e:
            raise HTTPException(status_code=409, detail=str(e)) from e
        # La llamada a Mercado Pago va en otro hilo: la pantalla y el bucle siguen respondiendo.
        outcome = await asyncio.to_thread(
            service.charge_yape, amount, reference, body.phone, body.otp
        )
        service.finish_yape(reference, amount, outcome)
        return service.snapshot()

    @app.post("/api/caja/accept-payment", dependencies=caja)
    async def accept_payment() -> dict:
        return act(service.accept_payment)

    @app.post("/api/recalibrate", dependencies=caja)
    async def recalibrate() -> dict:
        return act(service.recalibrate)

    @app.post("/api/recover", dependencies=caja)
    async def recover() -> dict:
        return act(service.recover)

    @app.post("/api/help")
    async def request_help() -> dict:
        service.request_help()
        return service.snapshot()

    @app.get("/api/sales", dependencies=caja)
    async def sales() -> dict:
        return service.pos.sales_today()

    @app.get("/api/help", dependencies=caja)
    async def list_help() -> list[dict]:
        return service.help_requests

    @app.delete("/api/help/{help_id}", dependencies=caja)
    async def resolve_help(help_id: int) -> list[dict]:
        if not service.resolve_help(help_id):
            raise HTTPException(status_code=404, detail="Esa solicitud de ayuda no existe")
        return service.help_requests

    @app.get("/api/alerts", dependencies=caja)
    async def list_alerts() -> list[dict]:
        return service.security_alerts

    @app.delete("/api/alerts/{alert_id}", dependencies=caja)
    async def resolve_alert(alert_id: int) -> list[dict]:
        if not service.resolve_alert(alert_id):
            raise HTTPException(status_code=404, detail="Esa alerta no existe")
        return service.security_alerts

    @app.websocket("/ws")
    async def ws(websocket: WebSocket) -> None:
        if not origin_ok(websocket.headers.get("origin"), websocket.headers.get("host")):
            await websocket.close(code=1008)
            return
        await websocket.accept()
        try:
            while True:
                await websocket.send_json(service.snapshot())
                await asyncio.sleep(TICK_S)
        except (WebSocketDisconnect, RuntimeError):
            pass

    @app.post("/api/cart/add")
    async def cart_add(body: SkuIn) -> dict:
        return act(lambda: service.add_product(body.sku))

    if recognizer is not None:
        last_seen: dict[str, str | None] = {"label": None}

        @app.post("/api/vision/frame")
        async def vision_frame(request: Request) -> dict:
            """Recibe el recuadro guía (JPEG/PNG) y devuelve el producto reconocido. No cambia la
            compra: la pantalla lo agrega cuando lo ve igual varias veces seguidas."""
            kind = request.headers.get("content-type", "").split(";")[0].strip()
            if kind not in ("image/jpeg", "image/png"):
                raise HTTPException(status_code=415, detail="Se espera una imagen JPEG o PNG")
            declared = request.headers.get("content-length", "")
            if declared.isdigit() and int(declared) > MAX_FRAME_BYTES:  # sin leerla entera
                raise HTTPException(status_code=413, detail="Imagen demasiado grande")
            data = await request.body()
            if len(data) > MAX_FRAME_BYTES:
                raise HTTPException(status_code=413, detail="Imagen demasiado grande")
            if service.checkout.state is not State.SCANNING:
                raise HTTPException(status_code=409, detail="La cámara solo reconoce al escanear")
            found = await asyncio.to_thread(recognizer.recognize_bytes, data)
            if found is None:
                raise HTTPException(status_code=422, detail="Imagen inválida")
            sku = found.sku
            product = service.catalog.get(sku)
            match = product is not None and found.match
            label = sku if match else "nada"
            if label != last_seen["label"]:  # solo los cambios: sirve para ajustar el umbral
                log.info(
                    "Recuadro: %s (mejor %s %.2f, margen %.2f)",
                    label,
                    sku,
                    found.score,
                    found.margin,
                )
                last_seen["label"] = label
            return {
                "match": match,
                "sku": sku if match else None,
                "name": product.name if match and product else None,
                "price_cents": product.price_cents if match and product else None,
                "score": round(found.score, 3),
                "margin": round(found.margin, 3),
            }

    if wallet_qr_file is not None:

        @app.get("/api/pay/wallet-qr")
        async def wallet_qr() -> FileResponse:
            return FileResponse(wallet_qr_file, headers={"Cache-Control": "no-store"})

    def notify(text: str, simulated: bool = False) -> dict:
        try:
            return service.wallet_notification(text, simulated=simulated)
        except TransitionError as e:
            raise HTTPException(status_code=409, detail=str(e)) from e

    if simulate_wallet:

        @app.post("/sim/wallet-notification")
        async def sim_wallet_notification(body: NotificationIn) -> dict:
            return notify(body.text, simulated=True)

    if notifier_key:

        @app.post("/api/pay/notification")
        async def pay_notification(
            body: NotificationIn, authorization: str | None = Header(default=None)
        ) -> dict:
            token = notifier_token(authorization) or notifier_token(body.key)
            if token is None or not hmac.compare_digest(token.encode(), notifier_key.encode()):
                # Se dice por qué, sin escribir la clave: ayuda a configurar el celular.
                log.warning("Notificación rechazada: %s", notifier_problem(token, notifier_key))
                raise HTTPException(status_code=401, detail="Clave del notificador inválida")
            return notify(body.text)

    if tray is not None and scale is not None:

        @app.get("/sim/catalog")
        async def sim_catalog() -> list[dict]:
            return [
                {"sku": p.sku, "name": p.name, "price_cents": p.price_cents, "weight_g": p.weight_g}
                for p in service.catalog.all()
            ]

        @app.post("/sim/tray")
        async def sim_tray(body: TrayIn) -> dict:
            try:
                tray.place(body.skus, body.hidden)
            except ValueError as e:
                raise HTTPException(status_code=422, detail=str(e)) from e
            return service.snapshot()

        def sim_change(action: Callable[[str], None], sku: str) -> dict:
            try:
                action(sku)
            except ValueError as e:
                raise HTTPException(status_code=422, detail=str(e)) from e
            return {"tray": tray.contents(), "camera": tray.in_view()}

        @app.get("/sim/tray")
        async def sim_tray_contents() -> dict:
            return {"tray": tray.contents(), "camera": tray.in_view()}

        @app.post("/sim/scale")
        async def sim_scale(body: ScaleIn) -> dict:
            return act(lambda: service.set_scale(scale if body.enabled else None))

        @app.post("/sim/scan")
        async def sim_scan(body: SkuIn) -> dict:
            return sim_change(tray.scan, body.sku)

        @app.post("/sim/sneak")
        async def sim_sneak(body: SkuIn) -> dict:
            return sim_change(tray.sneak, body.sku)

        @app.post("/sim/take")
        async def sim_take(body: SkuIn) -> dict:
            return sim_change(tray.take, body.sku)

        @app.post("/sim/trap")
        async def sim_trap(body: TrapIn) -> dict:
            scale.set_trap(body.offset_g)
            return service.snapshot()

    if ui_dir is not None:
        index = ui_dir / "index.html"

        @app.get("/ayuda", include_in_schema=False)
        async def ayuda_page() -> FileResponse:
            return FileResponse(index)

        # Al final: lo que no es de la API son archivos de la interfaz (/ → index.html).
        app.mount("/", StaticFiles(directory=ui_dir, html=True), name="ui")

    return app
