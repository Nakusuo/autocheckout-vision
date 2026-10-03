import asyncio
from collections.abc import Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from kiosk.checkout import TransitionError
from kiosk.scale import SimulatedScale
from kiosk.service import KioskService
from kiosk.tray import SimulatedTray

TICK_S = 0.2


class TrayIn(BaseModel):
    skus: list[str]


class TrapIn(BaseModel):
    offset_g: float


def create_app(
    service: KioskService,
    tray: SimulatedTray | None = None,
    scale: SimulatedScale | None = None,
    run_loop: bool = True,
) -> FastAPI:
    async def tick_loop() -> None:
        while True:
            service.tick()
            await asyncio.sleep(TICK_S)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        task = asyncio.create_task(tick_loop()) if run_loop else None
        yield
        if task:
            task.cancel()

    app = FastAPI(title="kiosk-api", lifespan=lifespan)

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
                tray.place(body.skus)
            except ValueError as e:
                raise HTTPException(status_code=422, detail=str(e)) from e
            return service.snapshot()

        @app.post("/sim/trap")
        async def sim_trap(body: TrapIn) -> dict:
            scale.set_trap(body.offset_g)
            return service.snapshot()

        @app.post("/sim/pay")
        async def sim_pay() -> dict:
            return act(service.simulate_payment)

    return app
