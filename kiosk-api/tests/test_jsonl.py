from pathlib import Path

from kiosk import jsonl
from kiosk.fusion import CartLine
from kiosk.metrics import SessionRecorder
from kiosk.pos import SimulatedPos

LINE = [CartLine("AGUA", "Agua", 1, 250)]


def test_rotates_past_the_limit_and_keeps_one_backup(tmp_path: Path):
    log = tmp_path / "log.jsonl"
    for i in range(8):  # 9 bytes por fila: rota antes de la 3 y de la 6
        jsonl.append(log, {"i": i}, max_bytes=20)
    assert jsonl.backup_of(log) == tmp_path / "log.1.jsonl"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["log.1.jsonl", "log.jsonl"]
    assert [r["i"] for r in jsonl.read_rows(log)] == [3, 4, 5, 6, 7]  # 0-2 ya se descartaron


def test_does_not_rotate_below_the_limit(tmp_path: Path):
    log = tmp_path / "log.jsonl"
    jsonl.append(log, {"i": 1}, max_bytes=1000)
    jsonl.append(log, {"i": 2}, max_bytes=1000)
    assert not jsonl.backup_of(log).exists()
    assert jsonl.read_rows(log) == [{"i": 1}, {"i": 2}]


def test_read_rows_of_missing_file_is_empty(tmp_path: Path):
    assert jsonl.read_rows(tmp_path / "nada.jsonl") == []


def test_receipt_numbers_survive_rotation(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(jsonl, "MAX_BYTES", 1)
    log = tmp_path / "boletas.jsonl"
    pos = SimulatedPos(log)
    pos.issue_receipt("venta-1", "ch_1", LINE, 250)
    pos.issue_receipt("venta-2", "ch_2", LINE, 250)
    # Con el log rotado, un quiosco reiniciado sigue la numeración.
    assert jsonl.backup_of(log).exists()
    again = SimulatedPos(log)
    assert again.issue_receipt("venta-3", "ch_3", LINE, 250)["number"] == "B001-00000003"


def test_memory_keeps_only_the_latest(monkeypatch):
    monkeypatch.setattr(jsonl, "KEEP_IN_MEMORY", 2)
    pos = SimulatedPos()
    rec = SessionRecorder()
    for i in range(3):
        pos.issue_receipt(f"venta-{i}", f"ch_{i}", LINE, 250)
        rec.begin(0.0)
        rec.finish(1.0, "paid", items=i)
    assert [r["reference"] for r in pos.receipts] == ["venta-1", "venta-2"]
    assert [s["items"] for s in rec.sessions] == [1, 2]
