import asyncio
import hmac
import logging
import time
from collections.abc import Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Protocol

from fastapi import FastAPI, Header, HTTPException, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field, StringConstraints
from starlette.responses import FileResponse, JSONResponse

from kiosk.checkout import TransitionError
from kiosk.scale import SimulatedScale
from kiosk.service import KioskService, Reading
from kiosk.tray import SimulatedTray

log = logging.getLogger(__name__)

TICK_S = 0.2
ALLOWED_ORIGINS = {"http://localhost:5173", "http://127.0.0.1:5173"}


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


class NotificationIn(BaseModel):
    """Texto de la notificación de pago recibido (Yape/Plin) tal como la muestra el celular."""

    text: str = Field(min_length=1, max_length=500)


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
) -> FastAPI:
    """threaded_sensing: la cámara se lee en otro hilo para que la pantalla y los botones no se
    congelen mientras se reconoce (~200 ms por cuadro); el estado solo cambia en este bucle.

    Demo web / app (cada parte se activa solo si se da):
    - `recognizer`: POST /api/vision/frame reconoce el recuadro guía que manda el navegador.
    - `wallet_qr_file`: GET /api/pay/wallet-qr sirve la imagen del QR de Yape/Plin del comercio.
    - `simulate_wallet`: POST /sim/wallet-notification simula la notificación de pago (demo).
    - `notifier_key`: POST /api/pay/notification para la futura app Android, con
      `Authorization: Bearer <clave>`; sin la clave correcta responde 401.
    """

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
        origin = request.headers.get("origin")
        if origin is not None and origin not in ALLOWED_ORIGINS:
            return JSONResponse({"detail": "Origen no permitido"}, status_code=403)
        return await call_next(request)

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

    @app.post("/api/caja/accept-payment")
    async def accept_payment() -> dict:
        return act(service.accept_payment)

    @app.post("/api/recalibrate")
    async def recalibrate() -> dict:
        return act(service.recalibrate)

    @app.post("/api/recover")
    async def recover() -> dict:
        return act(service.recover)

    @app.post("/api/help")
    async def request_help() -> dict:
        service.request_help()
        return service.snapshot()

    @app.get("/api/sales")
    async def sales() -> dict:
        return service.pos.sales_today()

    @app.get("/api/help")
    async def list_help() -> list[dict]:
        return service.help_requests

    @app.delete("/api/help/{help_id}")
    async def resolve_help(help_id: int) -> list[dict]:
        if not service.resolve_help(help_id):
            raise HTTPException(status_code=404, detail="Esa solicitud de ayuda no existe")
        return service.help_requests

    @app.get("/api/alerts")
    async def list_alerts() -> list[dict]:
        return service.security_alerts

    @app.delete("/api/alerts/{alert_id}")
    async def resolve_alert(alert_id: int) -> list[dict]:
        if not service.resolve_alert(alert_id):
            raise HTTPException(status_code=404, detail="Esa alerta no existe")
        return service.security_alerts

    @app.websocket("/ws")
    async def ws(websocket: WebSocket) -> None:
        origin = websocket.headers.get("origin")
        if origin is not None and origin not in ALLOWED_ORIGINS:
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
            data = await request.body()
            if len(data) > MAX_FRAME_BYTES:
                raise HTTPException(status_code=413, detail="Imagen demasiado grande")
            if service.snapshot()["screen"] != "W2":
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
                    "Recuadro: %s (mejor %s %.2f, margen %.2f)", label, sku, found.score, found.margin
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

    def notify(text: str) -> dict:
        try:
            return service.wallet_notification(text)
        except TransitionError as e:
            raise HTTPException(status_code=409, detail=str(e)) from e

    if simulate_wallet:

        @app.post("/sim/wallet-notification")
        async def sim_wallet_notification(body: NotificationIn) -> dict:
            return notify(body.text)

    if notifier_key:

        @app.post("/api/pay/notification")
        async def pay_notification(
            body: NotificationIn, authorization: str | None = Header(default=None)
        ) -> dict:
            scheme, _, token = (authorization or "").partition(" ")
            if scheme != "Bearer" or not hmac.compare_digest(token.encode(), notifier_key.encode()):
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

    return app
