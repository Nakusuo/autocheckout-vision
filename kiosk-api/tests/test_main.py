import pytest

from kiosk.__main__ import build_detector
from kiosk.catalog import Catalog, Product
from kiosk.scale import SimulatedScale
from kiosk.tray import SimulatedTray

CATALOG = Catalog([Product("AGUA", "Agua", 250, 651.0)])


def test_sim_mode_uses_tray():
    detector, tray = build_detector("sim", CATALOG, SimulatedScale(), {})
    assert isinstance(tray, SimulatedTray)
    assert detector is tray


def test_camera_mode_requires_model():
    with pytest.raises(SystemExit, match="KIOSK_MODEL"):
        build_detector("camera", CATALOG, SimulatedScale(), {})


def test_unknown_mode_exits():
    with pytest.raises(SystemExit, match="KIOSK_MODE"):
        build_detector("magia", CATALOG, SimulatedScale(), {})
