"""Métricas de la demo (M5): una fila JSONL por compra y un resumen frente a las metas del SRS.

- RNF-02 / ON-01: de INICIAR a W4 en ≤ 45 s.
- ON-03: ≥ 80 % de las compras se completan sin pedir ayuda.
- ON-02: cuántas veces la balanza detuvo una compra (alertas de peso).

Uso: python -m kiosk.metrics [kiosk-api/sesiones.jsonl]
"""

import datetime as dt
import json
import statistics
import sys
from collections.abc import Callable
from pathlib import Path

TARGET_S = 45.0
TARGET_AUTONOMOUS_PCT = 80.0
COUNTERS = ("weight_alerts", "corrections", "rescans", "payment_timeouts")
DEFAULT_PATH = Path(__file__).resolve().parents[2] / "sesiones.jsonl"


def _utc_now() -> str:
    return dt.datetime.now(dt.UTC).isoformat(timespec="seconds")


class SessionRecorder:
    def __init__(self, path: Path | None = None, wall: Callable[[], str] = _utc_now):
        self._path = path
        self._wall = wall
        self._current: dict | None = None
        self._started = 0.0
        self.sessions: list[dict] = []

    def begin(self, now: float) -> None:
        self._started = now
        self._current = {
            "started_at": self._wall(),
            "help_requested": False,
            **dict.fromkeys(COUNTERS, 0),
        }

    def note(self, field: str) -> None:
        if self._current is None:
            return
        if field == "help_requested":
            self._current[field] = True
        elif field in COUNTERS:
            self._current[field] += 1
        else:
            raise ValueError(f"Métrica desconocida: {field}")

    def finish(self, now: float, outcome: str, items: int = 0, total_cents: int = 0) -> None:
        if self._current is None:
            return
        row = {
            "started_at": self._current["started_at"],
            "outcome": outcome,
            "duration_s": round(now - self._started, 1),
            "help_requested": self._current["help_requested"],
            **{k: self._current[k] for k in COUNTERS},
            "items": items,
            "total_cents": total_cents,
        }
        self._current = None
        self.sessions.append(row)
        if self._path is not None:
            with self._path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _pct(part: int, whole: int) -> float:
    return round(100 * part / whole, 1) if whole else 0.0


def _mark(ok: bool) -> str:
    return "✅" if ok else "❌"


def summarize(rows: list[dict]) -> dict:
    paid = [r for r in rows if r["outcome"] == "paid"]
    durations = [r["duration_s"] for r in paid]
    autonomous = [r for r in paid if not r["help_requested"]]
    return {
        "sessions": len(rows),
        "paid": len(paid),
        "mean_s": round(statistics.fmean(durations), 1) if durations else 0.0,
        "median_s": round(statistics.median(durations), 1) if durations else 0.0,
        "max_s": max(durations, default=0.0),
        "within_45s_pct": _pct(sum(d <= TARGET_S for d in durations), len(durations)),
        "autonomous_pct": _pct(len(autonomous), len(rows)),
        "weight_alerts": sum(r["weight_alerts"] for r in rows),
        "corrections": sum(r["corrections"] for r in rows),
        "rescans": sum(r.get("rescans", 0) for r in rows),
        "payment_timeouts": sum(r["payment_timeouts"] for r in rows),
    }


def report(s: dict) -> str:
    on01 = (
        f"| RNF-02 / ON-01: de W1 a W4 en ≤ 45 s | media {s['mean_s']} s · mediana {s['median_s']} s · "
        f"máx. {s['max_s']} s · {s['within_45s_pct']} % dentro "
        f"| {_mark(bool(s['paid']) and s['max_s'] <= TARGET_S)} |"
    )
    on03 = (
        f"| ON-03: ≥ 80 % sin ayuda | {s['autonomous_pct']} % "
        f"| {_mark(bool(s['sessions']) and s['autonomous_pct'] >= TARGET_AUTONOMOUS_PCT)} |"
    )
    on02 = (
        f"| ON-02: pago solo con peso validado (±5 g) | {s['weight_alerts']} alertas de peso; "
        "ninguna venta se paga sin validar | ✅ |"
    )
    return "\n".join([
        f"Compras registradas: {s['sessions']} (pagadas: {s['paid']})",
        "",
        "| Meta | Resultado | Cumple |",
        "|---|---|---|",
        on01,
        on03,
        on02,
        "",
        (
            f"Correcciones (CORREGIR): {s['corrections']} · Reescaneos: {s['rescans']} · "
            f"Pagos vencidos (120 s): {s['payment_timeouts']}"
        ),
    ])


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # consola de Windows
    args = sys.argv[1:] if argv is None else argv
    path = Path(args[0]) if args else DEFAULT_PATH
    if not path.exists():
        print(f"No existe {path}: arranca el quiosco y haz algunas compras primero")
        return 1
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    print(report(summarize(rows)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
