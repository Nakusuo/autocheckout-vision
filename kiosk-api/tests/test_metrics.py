import json

import pytest

from kiosk.metrics import SessionRecorder, main, summarize


def paid(duration_s, help_requested=False, weight_alerts=0, items=1):
    return {
        "outcome": "paid",
        "duration_s": duration_s,
        "help_requested": help_requested,
        "weight_alerts": weight_alerts,
        "corrections": 0,
        "payment_timeouts": 0,
        "items": items,
        "total_cents": 250,
    }


def test_recorder_tracks_one_session_and_appends_jsonl(tmp_path):
    path = tmp_path / "sesiones.jsonl"
    rec = SessionRecorder(path, wall=lambda: "2026-10-10T10:00:00+00:00")
    rec.begin(100.0)
    rec.note("corrections")
    rec.note("weight_alerts")
    rec.note("weight_alerts")
    rec.note("help_requested")
    rec.finish(132.46, "paid", items=2, total_cents=530)

    row = json.loads(path.read_text(encoding="utf-8"))
    assert row == {
        "started_at": "2026-10-10T10:00:00+00:00",
        "outcome": "paid",
        "duration_s": 32.5,
        "help_requested": True,
        "weight_alerts": 2,
        "corrections": 1,
        "payment_timeouts": 0,
        "items": 2,
        "total_cents": 530,
    }
    assert rec.sessions == [row]


def test_recorder_ignores_notes_and_finish_without_session():
    rec = SessionRecorder()
    rec.note("help_requested")
    rec.finish(10.0, "fault")
    assert rec.sessions == []


def test_summary_against_srs_targets():
    rows = [paid(30.0), paid(40.0, weight_alerts=1), paid(50.0, help_requested=True), paid(44.0)]
    rows.append({**paid(20.0), "outcome": "fault"})
    s = summarize(rows)
    assert s["sessions"] == 5
    assert s["paid"] == 4
    assert s["mean_s"] == 41.0
    assert s["max_s"] == 50.0
    assert s["within_45s_pct"] == 75.0
    assert s["autonomous_pct"] == 60.0  # 3 de 5 sesiones pagadas sin ayuda
    assert s["weight_alerts"] == 1


def test_summary_of_nothing():
    assert summarize([])["sessions"] == 0


def test_main_prints_markdown_report(tmp_path, capsys):
    path = tmp_path / "sesiones.jsonl"
    path.write_text("\n".join(json.dumps(paid(d)) for d in (30.0, 40.0)) + "\n", encoding="utf-8")
    assert main([str(path)]) == 0
    out = capsys.readouterr().out
    assert "| RNF-02 / ON-01" in out
    assert "35.0 s" in out


def test_main_without_file_fails_clearly(tmp_path, capsys):
    assert main([str(tmp_path / "no-existe.jsonl")]) == 1
    assert "No existe" in capsys.readouterr().out


@pytest.mark.parametrize("field", ["weight_alerts", "corrections", "payment_timeouts", "help_requested"])
def test_recorder_accepts_known_notes(field):
    rec = SessionRecorder()
    rec.begin(0.0)
    rec.note(field)
    rec.finish(1.0, "paid", items=1, total_cents=1)
    assert rec.sessions[0][field] in (1, True)
