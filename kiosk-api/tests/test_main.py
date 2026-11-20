import pytest

from kiosk.__main__ import build_detector, scale_enabled
from kiosk.catalog import Catalog, Product
from kiosk.scale import SimulatedScale
from kiosk.tray import SimulatedTray

CATALOG = Catalog([Product("AGUA", "Agua", 250, 651.0)])


def test_sim_mode_uses_tray():
    detector, tray = build_detector("sim", CATALOG, SimulatedScale(), {})
    assert isinstance(tray, SimulatedTray)
    assert detector is tray


def test_camera_mode_requires_gallery_or_model():
    with pytest.raises(SystemExit, match="KIOSK_GALLERY"):
        build_detector("camera", CATALOG, SimulatedScale(), {})


def test_unknown_mode_exits():
    with pytest.raises(SystemExit, match="KIOSK_MODE"):
        build_detector("magia", CATALOG, SimulatedScale(), {})


def test_scale_is_off_by_default_and_can_be_simulated():
    assert scale_enabled({}) is False
    assert scale_enabled({"KIOSK_SCALE": "off"}) is False
    assert scale_enabled({"KIOSK_SCALE": "sim"}) is True


def test_unknown_scale_mode_exits():
    with pytest.raises(SystemExit, match="KIOSK_SCALE"):
        scale_enabled({"KIOSK_SCALE": "hx711"})


def test_server_address_defaults_to_localhost_and_reads_env():
    from kiosk.__main__ import server_address

    assert server_address({}) == ("127.0.0.1", 8000)
    assert server_address({"KIOSK_HOST": "0.0.0.0", "KIOSK_PORT": "9000"}) == ("0.0.0.0", 9000)


@pytest.mark.parametrize("port", ["abc", "0", "70000", "-1"])
def test_invalid_port_exits(port):
    from kiosk.__main__ import server_address

    with pytest.raises(SystemExit, match="KIOSK_PORT"):
        server_address({"KIOSK_PORT": port})


def test_data_dir_is_created_from_env(tmp_path):
    from kiosk.__main__ import REPO, data_dir

    target = tmp_path / "datos" / "quiosco"
    assert data_dir({"KIOSK_DATA_DIR": str(target)}) == target
    assert target.is_dir()
    assert data_dir({}) == REPO / "kiosk-api"


def test_gateway_ca_dev_uses_dev_ca(tmp_path):
    from kiosk.__main__ import gateway_ca

    (tmp_path / "ca.pem").write_text("ca")
    assert gateway_ca({}, tmp_path) == tmp_path / "ca.pem"
    assert gateway_ca({"GATEWAY_CA": "dev"}, tmp_path) == tmp_path / "ca.pem"


def test_gateway_ca_dev_without_ca_exits(tmp_path):
    from kiosk.__main__ import gateway_ca

    with pytest.raises(SystemExit, match="devkeys"):
        gateway_ca({}, tmp_path)


def test_gateway_ca_system_trusts_system_store(tmp_path):
    from kiosk.__main__ import gateway_ca

    assert gateway_ca({"GATEWAY_CA": "system"}, tmp_path) is None


def test_unknown_gateway_ca_exits(tmp_path):
    from kiosk.__main__ import gateway_ca

    with pytest.raises(SystemExit, match="GATEWAY_CA"):
        gateway_ca({"GATEWAY_CA": "cualquiera"}, tmp_path)
