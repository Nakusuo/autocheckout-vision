import pytest

from kiosk.checkout import Checkout, State, TransitionError
from kiosk.fusion import Cart, CartLine, WeightCheck

ONE_ITEM = Cart((CartLine("AGUA", "Agua", 1, 250),), 651.0, 250, ())
FOUR_ITEMS = Cart((CartLine("CHOCO", "Chocolate", 4, 280),), 132.0, 1120, ())
EMPTY = Cart((), 0.0, 0, ())
WITH_UNKNOWN = Cart((CartLine("AGUA", "Agua", 1, 250),), 651.0, 250, ("FANTASMA",))
OK = WeightCheck(True, 1.0)
BAD = WeightCheck(False, 30.0)


def scanning(cart=ONE_ITEM, weight=OK) -> Checkout:
    c = Checkout()
    c.start()
    c.update(cart, weight)
    return c


def test_happy_path_w1_to_w4_and_back():
    c = scanning()
    c.confirm()
    assert c.state is State.CONFIRMING and c.can_pay
    c.pay()
    assert c.state is State.PAYING
    c.payment_confirmed()
    assert c.state is State.PAID
    c.reset()
    assert c.state is State.IDLE and c.cart is None


@pytest.mark.parametrize("cart", [EMPTY, FOUR_ITEMS, WITH_UNKNOWN])
def test_confirm_requires_one_to_three_valid_items(cart):
    c = scanning(cart)
    with pytest.raises(TransitionError):
        c.confirm()
    assert c.state is State.SCANNING


def test_pay_blocked_when_weight_mismatch():
    c = scanning(weight=BAD)
    c.confirm()
    assert c.can_pay is False
    with pytest.raises(TransitionError):
        c.pay()


def test_correct_returns_to_scanning():
    c = scanning()
    c.confirm()
    c.correct()
    assert c.state is State.SCANNING


def test_payment_timeout_returns_to_confirming():
    c = scanning()
    c.confirm()
    c.pay()
    c.payment_timeout()
    assert c.state is State.CONFIRMING


def test_fault_from_any_state_and_recover_to_idle():
    c = scanning()
    c.fault()
    assert c.state is State.OUT_OF_SERVICE
    c.recover()
    assert c.state is State.IDLE and c.cart is None


def test_invalid_transition_raises():
    with pytest.raises(TransitionError):
        Checkout().pay()
