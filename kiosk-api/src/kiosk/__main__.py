from pathlib import Path

import uvicorn

from kiosk.app import create_app
from kiosk.scale import SimulatedScale
from kiosk.service import KioskService
from kiosk.store import init_db, load_catalog
from kiosk.tray import SimulatedTray

REPO = Path(__file__).resolve().parents[3]


def main() -> None:
    db = REPO / "kiosk-api" / "kiosk.db"
    init_db(db, REPO / "catalog" / "products.csv")
    catalog = load_catalog(db)
    scale = SimulatedScale()
    tray = SimulatedTray(catalog, scale)
    service = KioskService(catalog, tray, scale)
    uvicorn.run(create_app(service, tray, scale), host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
