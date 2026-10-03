import pytest

from kiosk.catalog import Catalog, Product
from kiosk.scale import SimulatedScale
from kiosk.tray import Detector, ScaleFollowingDetector, SimulatedTray

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


class FixedDetector:
    def __init__(self, skus: list[str]):
        self.skus = skus

    def detect(self) -> list[str]:
        return list(self.skus)


def test_scale_follows_detections():
    scale = SimulatedScale(noise_g=0)
    detector = ScaleFollowingDetector(FixedDetector(["AGUA", "CHOCO"]), CATALOG, scale)
    assert detector.detect() == ["AGUA", "CHOCO"]
    assert scale.read() == 684.0


def test_unknown_detection_weighs_nothing():
    scale = SimulatedScale(noise_g=0)
    detector = ScaleFollowingDetector(FixedDetector(["AGUA", "OTRA"]), CATALOG, scale)
    detector.detect()
    assert scale.read() == 651.0
