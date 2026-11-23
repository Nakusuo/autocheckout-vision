import datetime as dt
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from payment_helpers import PUBLIC_PEM, FakeGateway

from kiosk.app import create_app
from kiosk.catalog import Catalog, Product
from kiosk.fusion import CartLine
from kiosk.metrics import SessionRecorder, report, summarize
from kiosk.payments import JwtVerifier
from kiosk.pos import SimulatedPos, payment_method
from kiosk.scale import SimulatedScale
from kiosk.service import KioskService
from kiosk.tray import SimulatedTray

LINES = [CartLine("AGUA", "Agua", 2, 250), CartLine("CHOCO", "Chocolate", 1, 280)]
TODAY = dt.datetime(2026, 10, 12, 15, 0).astimezone()


def stamp(when: dt.datetime):
    return lambda: when.isoformat(timespec="seconds")


def test_sales_today_counts_only_today_newest_first(tmp_path: Path):
    log = tmp_path / "boletas.jsonl"
    SimulatedPos(log, now=stamp(TODAY - dt.timedelta(days=1))).issue_receipt(
        "v-0", "c0", LINES, 780
    )
    pos = SimulatedPos(log, now=stamp(TODAY))
    pos.issue_receipt("v-1", "c1", LINES, 780)
    pos.issue_receipt("v-2", "c2", LINES[:1], 500)
    sales = SimulatedPos(log).sales_today(TODAY.date())  # otro arranque: lee el archivo
    assert (sales["count"], sales["total_cents"]) == (2, 1280)
    assert sales["receipts"] == [
        {
            "number": "B001-00000003",
            "issued_at": TODAY.isoformat(timespec="seconds"),
            "items": 2,
            "total_cents": 500,
            "lines": [{"name": LINES[0].name, "quantity": LINES[0].quantity}],
            "payer": None,
            "method": "Pasarela",
        },
        {
            "number": "B001-00000002",
            "issued_at": TODAY.isoformat(timespec="seconds"),
            "items": 3,
            "total_cents": 780,
            "lines": [{"name": line.name, "quantity": line.quantity} for line in LINES],
            "payer": None,
            "method": "Pasarela",
        },
    ]


def test_sales_today_in_memory_and_limit():
    pos = SimulatedPos(now=stamp(TODAY))
    for i in range(3):
        pos.issue_receipt(f"v-{i}", f"c{i}", LINES, 780)
    sales = pos.sales_today(TODAY.date(), limit=2)
    assert sales["count"] == 3
    assert [r["number"] for r in sales["receipts"]] == ["B001-00000003", "B001-00000002"]


@pytest.mark.parametrize(
    ("charge_id", "method"),
    [
        ("sim-billetera-v1", "Simulado"),
        ("caja-billetera-v1", "Aprobado en caja"),
        ("billetera-v1", "Yape (notificación)"),
        ("ch_1", "Pasarela"),
    ],
)
def test_payment_method_comes_from_the_charge_id(charge_id, method):
    assert payment_method(charge_id) == method


def test_receipt_keeps_the_payer():
    pos = SimulatedPos(now=stamp(TODAY))
    pos.issue_receipt("v-1", "billetera-v-1", LINES, 780, payer="Ana")
    assert pos.sales_today(TODAY.date())["receipts"][0]["payer"] == "Ana"


def test_sales_today_defaults_to_the_local_date():
    pos = SimulatedPos()
    pos.issue_receipt("v-1", "c1", LINES, 780)
    assert pos.sales_today()["count"] == 1


def test_api_sales_endpoint():
    catalog = Catalog([Product("AGUA", "Agua", 250, 651.0)])
    tray = SimulatedTray(catalog, SimulatedScale(noise_g=0))
    svc = KioskService(catalog, tray, None, FakeGateway(), JwtVerifier(PUBLIC_PEM))
    client = TestClient(create_app(svc, tray, None, run_loop=False))
    assert client.get("/api/sales").json() == {"count": 0, "total_cents": 0, "receipts": []}


def test_cancel_records_the_screen_and_report_groups_them():
    catalog = Catalog([Product("AGUA", "Agua", 250, 651.0)])
    tray = SimulatedTray(catalog, SimulatedScale(noise_g=0))
    svc = KioskService(catalog, tray, None, FakeGateway(), JwtVerifier(PUBLIC_PEM))
    svc.start()
    svc.cancel()
    svc.start()
    tray.place(["AGUA"])
    for _ in range(3):
        svc.tick()
    svc.confirm()
    svc.cancel()
    assert [r["screen"] for r in svc.sessions.sessions] == ["W2", "W3"]
    s = summarize(svc.sessions.sessions)
    assert s["cancelled_on"] == {"W2": 1, "W3": 1}
    assert "Cancelaciones por pantalla: W2 1 · W3 1" in report(s)


def test_report_without_cancellations_and_old_rows():
    rec = SessionRecorder()
    rec.begin(0.0)
    rec.finish(10.0, "paid", 1, 250)
    assert "screen" not in rec.sessions[0]
    assert "Cancelaciones por pantalla: ninguna" in report(summarize(rec.sessions))
    old = {**rec.sessions[0], "outcome": "cancelled"}  # fila de antes, sin pantalla
    assert summarize([old])["cancelled_on"] == {"?": 1}
