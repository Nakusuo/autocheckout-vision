"""POS simulado: emite la boleta de cada venta pagada y la deja en un log JSONL.

La boleta electrónica de SUNAT y el POS real de la tienda quedan fuera del MVP.
"""

import datetime as dt
import logging
from collections.abc import Callable, Iterable
from pathlib import Path

from kiosk import jsonl
from kiosk.fusion import CartLine

log = logging.getLogger(__name__)

SERIES = "B001"


def _utc_now() -> str:
    return dt.datetime.now(dt.UTC).isoformat(timespec="seconds")


def payment_method(charge_id: str) -> str:
    """Cómo se pagó, según el identificador del cobro guardado en la boleta."""
    if charge_id.startswith("sim-"):
        return "Simulado"
    if charge_id.startswith("caja-"):
        return "Aprobado en caja"
    if charge_id.startswith("billetera-"):
        return "Yape (notificación)"
    return "Pasarela"


class SimulatedPos:
    def __init__(self, path: Path | None = None, now: Callable[[], str] = _utc_now):
        self._path = path
        self._now = now
        self.receipts: list[dict] = []
        self._last = 0
        if path is not None:
            # La numeración sigue a la última boleta guardada, aunque el log se haya rotado.
            rows = jsonl.read_rows(path)
            self._last = int(rows[-1]["number"].rsplit("-", 1)[1]) if rows else 0

    def issue_receipt(
        self,
        reference: str,
        charge_id: str,
        lines: Iterable[CartLine],
        total_cents: int,
        payer: str | None = None,
    ) -> dict:
        """Emite la boleta simulada. `payer` es el nombre que trajo la notificación de Yape."""
        self._last += 1
        receipt = {
            "number": f"{SERIES}-{self._last:08d}",
            "issued_at": self._now(),
            "reference": reference,
            "charge_id": charge_id,
            "lines": [
                {
                    "sku": line.sku,
                    "name": line.name,
                    "quantity": line.quantity,
                    "unit_price_cents": line.unit_price_cents,
                }
                for line in lines
            ],
            "total_cents": total_cents,
        }
        if payer is not None:
            receipt["payer"] = payer
        self.receipts.append(receipt)
        del self.receipts[: -jsonl.KEEP_IN_MEMORY]
        if self._path is not None:
            jsonl.append(self._path, receipt)
        log.info("Boleta simulada %s por %d céntimos", receipt["number"], total_cents)
        return receipt

    def sales_today(self, today: dt.date | None = None, limit: int = 20) -> dict:
        """Resumen para la caja: ventas del día (hora local) y las últimas boletas con su detalle
        (productos, quién pagó y cómo)."""
        rows = jsonl.read_rows(self._path) if self._path is not None else self.receipts
        day = today or dt.datetime.now().astimezone().date()
        mine = [
            r for r in rows if dt.datetime.fromisoformat(r["issued_at"]).astimezone().date() == day
        ]
        return {
            "count": len(mine),
            "total_cents": sum(r["total_cents"] for r in mine),
            "receipts": [
                {
                    "number": r["number"],
                    "issued_at": r["issued_at"],
                    "items": sum(line["quantity"] for line in r["lines"]),
                    "total_cents": r["total_cents"],
                    "lines": [
                        {"name": line["name"], "quantity": line["quantity"]} for line in r["lines"]
                    ],
                    "payer": r.get("payer"),
                    "method": payment_method(r["charge_id"]),
                }
                for r in reversed(mine[-limit:])
            ],
        }
