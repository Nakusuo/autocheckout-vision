import pytest

from kiosk.catalog import Catalog, Product
from kiosk.scale import SimulatedScale
from kiosk.tray import Detector, SimulatedTray

CATALOG = Catalog([Product("AGUA", "Agua", 250, 651.0), Product("CHOCO", "Chocolate", 280, 33.0)])


def make() -> tuple[SimulatedTray, SimulatedScale]:
    scale = SimulatedScale(noise_g=0)
    return SimulatedTray(CATALOG, scale), scale


def test_place_is_detected_and_loads_scale():
    tray, scale = make()
    tray.place(["AGUA", "CHOCO"])

    assert tray.detect() == ["AGUA", "CHOCO"]
    assert scale.read() == 684.0


def test_unknown_sku_is_rejected():
    tray, _ = make()
    with pytest.raises(ValueError, match="FANTASMA"):
        tray.place(["FANTASMA"])


def test_empty_tray():
    tray, scale = make()
    tray.place([])
    assert tray.detect() == []
    assert scale.read() == 0.0


def test_satisfies_detector_protocol():
    tray, _ = make()
    assert isinstance(tray, Detector)


def test_hidden_products_weigh_but_are_not_detected():
    tray, scale = make()
    tray.place(["AGUA"], hidden=["CHOCO"])
    assert tray.detect() == ["AGUA"]
    assert scale.read() == 684.0


def test_unknown_hidden_sku_is_rejected():
    tray, _ = make()
    with pytest.raises(ValueError, match="FANTASMA"):
        tray.place([], hidden=["FANTASMA"])


class Clock:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t


def test_scan_shows_the_product_briefly_and_leaves_it_on_the_tray():
    clock = Clock()
    scale = SimulatedScale(noise_g=0)
    tray = SimulatedTray(CATALOG, scale, clock=clock, show_s=1.5)
    tray.scan("AGUA")
    assert tray.detect() == ["AGUA"]
    assert scale.read() == 651.0
    clock.t = 1.6
    assert tray.detect() == []
    assert tray.contents() == ["AGUA"]


def test_sneak_weighs_without_being_seen_and_take_removes():
    tray, scale = make()
    tray.sneak("CHOCO")
    assert tray.detect() == []
    assert scale.read() == 33.0
    tray.take("CHOCO")
    assert scale.read() == 0.0
    with pytest.raises(ValueError, match="CHOCO"):
        tray.take("CHOCO")
