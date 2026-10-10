import asyncio
import logging
from collections.abc import Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from starlette.responses import JSONResponse

from kiosk.checkout import TransitionError
from kiosk.scale import SimulatedScale
from kiosk.service import KioskService
from kiosk.tray import SimulatedTray

log = logging.getLogger(__name__)

TICK_S = 0.2
ALLOWED_ORIGINS = {"http://localhost:5173", "http://127.0.0.1:5173"}


class TrayIn(BaseModel):
    skus: list[str]
    hidden: list[str] = []


class SkuIn(BaseModel):
    sku: str


class TrapIn(BaseModel):
    offset_g: float = Field(ge=-5000, le=5000)


def safe_tick(service: KioskService) -> None:
    try:
        service.tick()
    except Exception:
        log.exception("Error en tick; el bucle sigue")


def create_app(
    service: KioskService,
    tray: SimulatedTray | None = None,
    scale: SimulatedScale | None = None,
    run_loop: bool = True,
) -> FastAPI:
    async def tick_loop() -> None:
        while True:
            safe_tick(service)
            await asyncio.sleep(TICK_S)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        task = asyncio.create_task(tick_loop()) if run_loop else None
        yield
        if task:
            task.cancel()

    app = FastAPI(title="kiosk-api", lifespan=lifespan)

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

    @app.post("/api/recover")
    async def recover() -> dict:
        return act(service.recover)

    @app.post("/api/help")
    async def request_help() -> dict:
        service.request_help()
        return service.snapshot()

    @app.get("/api/help")
    async def list_help() -> list[dict]:
        return service.help_requests

    @app.delete("/api/help/{help_id}")
    async def resolve_help(help_id: int) -> list[dict]:
        service.resolve_help(help_id)
        return service.help_requests

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
            return {"tray": tray.contents()}

        @app.get("/sim/tray")
        async def sim_tray_contents() -> dict:
            return {"tray": tray.contents()}

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
