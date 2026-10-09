import json

from kiosk.fusion import CartLine
from kiosk.pos import SimulatedPos

LINES = (CartLine("AGUA", "Agua", 2, 250),)


def test_issues_numbered_receipts_and_appends_jsonl(tmp_path):
    path = tmp_path / "boletas.jsonl"
    pos = SimulatedPos(path, now=lambda: "2026-10-09T12:00:00+00:00")

    first = pos.issue_receipt("venta-1", "ch_1", LINES, 500)
    second = pos.issue_receipt("venta-2", "ch_2", LINES, 500)

    assert first["number"] == "B001-00000001"
    assert second["number"] == "B001-00000002"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert rows[0] == {
        "number": "B001-00000001",
        "issued_at": "2026-10-09T12:00:00+00:00",
        "reference": "venta-1",
        "charge_id": "ch_1",
        "lines": [{"sku": "AGUA", "name": "Agua", "quantity": 2, "unit_price_cents": 250}],
        "total_cents": 500,
    }
    assert pos.receipts == rows


def test_continues_numbering_after_restart(tmp_path):
    path = tmp_path / "boletas.jsonl"
    SimulatedPos(path).issue_receipt("venta-1", "ch_1", LINES, 500)
    again = SimulatedPos(path).issue_receipt("venta-1", "ch_9", LINES, 500)
    assert again["number"] == "B001-00000002"


def test_without_file_keeps_receipts_in_memory():
    pos = SimulatedPos()
    pos.issue_receipt("venta-1", "ch_1", LINES, 500)
    assert [r["number"] for r in pos.receipts] == ["B001-00000001"]
