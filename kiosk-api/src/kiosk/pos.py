"""POS simulado: emite la boleta de cada venta pagada y la deja en un log JSONL.

La boleta electrónica de SUNAT y el POS real de la tienda quedan fuera del MVP.
"""

import datetime as dt
import json
import logging
from collections.abc import Callable, Iterable
from pathlib import Path

from kiosk.fusion import CartLine

log = logging.getLogger(__name__)

SERIES = "B001"


def _utc_now() -> str:
    return dt.datetime.now(dt.UTC).isoformat(timespec="seconds")


class SimulatedPos:
    def __init__(self, path: Path | None = None, now: Callable[[], str] = _utc_now):
        self._path = path
        self._now = now
        self.receipts: list[dict] = []
        self._last = 0
        if path is not None and path.exists():
            self._last = sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line)

    def issue_receipt(
        self, reference: str, charge_id: str, lines: Iterable[CartLine], total_cents: int
    ) -> dict:
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
        self.receipts.append(receipt)
        if self._path is not None:
            with self._path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(receipt, ensure_ascii=False) + "\n")
        log.info("Boleta simulada %s por %d céntimos", receipt["number"], total_cents)
        return receipt
