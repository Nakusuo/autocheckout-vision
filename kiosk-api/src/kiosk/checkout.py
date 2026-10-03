from enum import Enum

from kiosk.fusion import Cart, WeightCheck

MAX_ITEMS = 3


class State(str, Enum):
    IDLE = "IDLE"  # W1
    SCANNING = "SCANNING"  # W2
    CONFIRMING = "CONFIRMING"  # W3
    PAYING = "PAYING"  # QR
    PAID = "PAID"  # W4
    OUT_OF_SERVICE = "OUT_OF_SERVICE"


class TransitionError(Exception):
    pass


class Checkout:
    def __init__(self) -> None:
        self.state = State.IDLE
        self.cart: Cart | None = None
        self.weight: WeightCheck | None = None

    def _require(self, *states: State) -> None:
        if self.state not in states:
            raise TransitionError(f"Acción no permitida en el estado {self.state.value}")

    def _clear(self) -> None:
        self.cart = None
        self.weight = None

    @property
    def can_pay(self) -> bool:
        return self.state is State.CONFIRMING and self.weight is not None and self.weight.ok

    def start(self) -> None:
        self._require(State.IDLE)
        self.state = State.SCANNING

    def update(self, cart: Cart, weight: WeightCheck) -> None:
        self._require(State.SCANNING, State.CONFIRMING)
        self.cart = cart
        self.weight = weight

    def confirm(self) -> None:
        self._require(State.SCANNING)
        cart = self.cart
        if cart is None or cart.unknown_skus or not 1 <= cart.item_count <= MAX_ITEMS:
            raise TransitionError("Se necesitan de 1 a 3 productos reconocidos")
        self.state = State.CONFIRMING

    def correct(self) -> None:
        self._require(State.CONFIRMING)
        self.state = State.SCANNING

    def pay(self) -> None:
        self._require(State.CONFIRMING)
        if not self.can_pay:
            raise TransitionError("Revise su bandeja")
        self.state = State.PAYING

    def payment_confirmed(self) -> None:
        self._require(State.PAYING)
        self.state = State.PAID

    def payment_timeout(self) -> None:
        self._require(State.PAYING)
        self.state = State.CONFIRMING

    def reset(self) -> None:
        self._require(State.PAID)
        self._clear()
        self.state = State.IDLE

    def fault(self) -> None:
        self.state = State.OUT_OF_SERVICE

    def recover(self) -> None:
        self._require(State.OUT_OF_SERVICE)
        self._clear()
        self.state = State.IDLE
