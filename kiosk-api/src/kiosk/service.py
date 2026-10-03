import logging
import time
from collections.abc import Callable

from kiosk.catalog import Catalog
from kiosk.checkout import MAX_ITEMS, Checkout, State
from kiosk.fusion import build_cart, check_weight
from kiosk.scale import ScaleReader
from kiosk.stability import StabilityFilter
from kiosk.tray import Detector

log = logging.getLogger(__name__)

RESET_AFTER_S = 10.0
PAYMENT_TIMEOUT_S = 120.0

SCREEN = {
    State.IDLE: "W1",
    State.SCANNING: "W2",
    State.CONFIRMING: "W3",
    State.PAYING: "QR",
    State.PAID: "W4",
    State.OUT_OF_SERVICE: "FUERA_DE_SERVICIO",
}


class KioskService:
    def __init__(
        self,
        catalog: Catalog,
        detector: Detector,
        scale: ScaleReader,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.catalog = catalog
        self._detector = detector
        self._scale = scale
        self._clock = clock
        self.checkout = Checkout()
        self._stability = StabilityFilter()
        self._entered_at = clock()
        self.help_requests: list[dict] = []
        self._next_help_id = 1

    def _do(self, action: Callable[[], None]) -> None:
        before = self.checkout.state
        action()
        if self.checkout.state is not before:
            self._entered_at = self._clock()
            if self.checkout.state is State.SCANNING:
                self._stability.reset()

    def start(self) -> None:
        self._do(self.checkout.start)

    def confirm(self) -> None:
        self._do(self.checkout.confirm)

    def correct(self) -> None:
        self._do(self.checkout.correct)

    def pay(self) -> None:
        self._do(self.checkout.pay)

    def simulate_payment(self) -> None:
        self._do(self.checkout.payment_confirmed)

    def recover(self) -> None:
        self._do(self.checkout.recover)

    def tick(self) -> None:
        state = self.checkout.state
        elapsed = self._clock() - self._entered_at
        if state is State.PAID and elapsed >= RESET_AFTER_S:
            self._do(self.checkout.reset)
            return
        if state is State.PAYING and elapsed >= PAYMENT_TIMEOUT_S:
            self._do(self.checkout.payment_timeout)
            return
        if state not in (State.SCANNING, State.CONFIRMING):
            return
        try:
            skus = self._detector.detect()
            grams = self._scale.read()
        except Exception:
            log.exception("Fallo de sensor; quiosco fuera de servicio")
            self._do(self.checkout.fault)
            return
        stable = self._stability.push(skus)
        if stable is None:
            return
        cart = build_cart(stable, self.catalog)
        if state is State.CONFIRMING and cart != self.checkout.cart:
            self._do(self.checkout.correct)
        self.checkout.update(cart, check_weight(cart.theoretical_weight_g, grams))

    def request_help(self) -> dict:
        req = {
            "id": self._next_help_id,
            "screen": SCREEN[self.checkout.state],
            "at": self._clock(),
        }
        self._next_help_id += 1
        self.help_requests.append(req)
        return req

    def resolve_help(self, help_id: int) -> None:
        self.help_requests = [r for r in self.help_requests if r["id"] != help_id]

    def _alert(self) -> str | None:
        cart, weight = self.checkout.cart, self.checkout.weight
        if cart is None:
            return None
        if cart.item_count > MAX_ITEMS:
            return "Para más de 3 productos use la caja"
        if cart.unknown_skus:
            return "Hay un producto que no reconocemos"
        if weight is not None and not weight.ok:
            return "Revise su bandeja"
        return None

    def snapshot(self) -> dict:
        c = self.checkout
        cart = c.cart
        return {
            "state": c.state.value,
            "screen": SCREEN[c.state],
            "can_pay": c.can_pay,
            "lines": [
                {
                    "sku": line.sku,
                    "name": line.name,
                    "quantity": line.quantity,
                    "unit_price_cents": line.unit_price_cents,
                }
                for line in (cart.lines if cart else ())
            ],
            "total_cents": cart.total_cents if cart else 0,
            "item_count": cart.item_count if cart else 0,
            "weight": {"ok": c.weight.ok, "diff_g": c.weight.diff_g} if c.weight else None,
            "alert": self._alert(),
            "seconds_in_state": round(self._clock() - self._entered_at, 1),
            "help_pending": bool(self.help_requests),
        }
