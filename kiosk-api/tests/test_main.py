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


def test_payment_mode_defaults_to_qr():
    from kiosk.__main__ import payment_mode

    assert payment_mode({}) == "qr"
    assert payment_mode({"KIOSK_PAYMENT": "yape"}) == "yape"
    with pytest.raises(SystemExit, match="KIOSK_PAYMENT"):
        payment_mode({"KIOSK_PAYMENT": "tarjeta"})


YAPE_ENV = {"MP_PUBLIC_KEY": "TEST-pk", "MP_ACCESS_TOKEN": "TEST-token"}


@pytest.mark.parametrize("missing", ["MP_PUBLIC_KEY", "MP_ACCESS_TOKEN"])
def test_build_yape_requires_credentials(tmp_path, missing):
    from kiosk.__main__ import build_yape

    env = {k: v for k, v in YAPE_ENV.items() if k != missing}
    with pytest.raises(SystemExit, match="MP_PUBLIC_KEY y MP_ACCESS_TOKEN"):
        build_yape(env, tmp_path)


@pytest.mark.parametrize("url", ["http://api.mercadopago.com", "ftp://x", "https://"])
def test_build_yape_requires_https(tmp_path, url):
    from kiosk.__main__ import build_yape

    with pytest.raises(SystemExit, match="https"):
        build_yape({**YAPE_ENV, "MP_BASE_URL": url}, tmp_path)


def test_build_yape_against_mercado_pago_uses_system_cas(tmp_path, monkeypatch):
    import kiosk.__main__ as main

    seen = {}
    monkeypatch.setattr(main, "MercadoPagoYape", lambda *a, **kw: seen.update(args=a, kw=kw))
    main.build_yape(YAPE_ENV, tmp_path)  # sin ca.pem: no hace falta con Mercado Pago real
    assert seen["args"] == ("https://api.mercadopago.com", "TEST-pk", "TEST-token")
    assert seen["kw"] == {"payer_email": "cliente@autocaja.pe", "ca_file": None}


def test_build_yape_against_the_mock_uses_the_dev_ca(tmp_path, monkeypatch):
    import kiosk.__main__ as main

    (tmp_path / "ca.pem").write_text("ca")
    seen = {}
    monkeypatch.setattr(main, "MercadoPagoYape", lambda *a, **kw: seen.update(args=a, kw=kw))
    env = {**YAPE_ENV, "MP_BASE_URL": "https://mock-gateway:8443", "MP_PAYER_EMAIL": "a@b.pe"}
    main.build_yape(env, tmp_path)
    assert seen["args"][0] == "https://mock-gateway:8443"
    assert seen["kw"] == {"payer_email": "a@b.pe", "ca_file": tmp_path / "ca.pem"}


def test_build_yape_returns_a_real_client(tmp_path):
    from kiosk.__main__ import build_yape
    from kiosk.payments import MercadoPagoYape

    assert isinstance(build_yape(YAPE_ENV, tmp_path), MercadoPagoYape)


def test_no_qr_gateway_refuses_qr():
    from kiosk.__main__ import NoQrGateway
    from kiosk.payments import PaymentError

    with pytest.raises(PaymentError, match="Yape"):
        NoQrGateway().create_charge(100, "venta-1")
    assert NoQrGateway().poll("x") is None
    with pytest.raises(PaymentError, match="no con QR"):
        NoQrGateway().confirm("x")  # la caja no puede aprobar un QR que no existe


def test_background_mode_defaults_to_fixed_tray(tmp_path):
    from kiosk.__main__ import background_segmenter

    assert background_segmenter({}) is None
    assert background_segmenter({"KIOSK_FONDO": "fijo"}) is None


def test_free_background_needs_the_segmenter_model(tmp_path):
    from kiosk.__main__ import background_segmenter

    model = tmp_path / "silueta.onnx"
    with pytest.raises(SystemExit, match="falta el modelo"):
        background_segmenter({"KIOSK_FONDO": "libre", "KIOSK_SEGMENTER": str(model)})
    model.write_bytes(b"x")
    assert background_segmenter({"KIOSK_FONDO": "libre", "KIOSK_SEGMENTER": str(model)}) == model


def test_unknown_background_mode_exits():
    from kiosk.__main__ import background_segmenter

    with pytest.raises(SystemExit, match="KIOSK_FONDO"):
        background_segmenter({"KIOSK_FONDO": "verde"})


def test_payment_mode_accepts_own_wallet_qr():
    from kiosk.__main__ import payment_mode

    assert payment_mode({"KIOSK_PAYMENT": "yape-qr"}) == "yape-qr"


def test_wallet_settings(tmp_path):
    from kiosk.__main__ import wallet_settings

    qr = tmp_path / "mi-qr.png"
    with pytest.raises(SystemExit, match="falta la imagen"):
        wallet_settings({"KIOSK_YAPE_QR": str(qr)})
    qr.write_bytes(b"png")
    assert wallet_settings({"KIOSK_YAPE_QR": str(qr)}) == (qr, False, None)
    env = {"KIOSK_YAPE_QR": str(qr), "KIOSK_SIMULAR_PAGO": "on", "KIOSK_NOTIFIER_KEY": "k" * 16}
    assert wallet_settings(env) == (qr, True, "k" * 16)
    with pytest.raises(SystemExit, match="16 caracteres"):
        wallet_settings({"KIOSK_YAPE_QR": str(qr), "KIOSK_NOTIFIER_KEY": "corta"})
    txt = tmp_path / "qr.txt"
    txt.write_text("x")
    with pytest.raises(SystemExit, match="PNG o JPG"):
        wallet_settings({"KIOSK_YAPE_QR": str(txt)})


def test_wallet_settings_default_path_is_private_folder(tmp_path, monkeypatch):
    import kiosk.__main__ as main

    monkeypatch.setattr(main, "REPO", tmp_path)
    with pytest.raises(SystemExit, match=str(tmp_path / "privado" / "yape-qr.png")):
        main.wallet_settings({})


def test_web_mode_has_no_kiosk_camera():
    from kiosk.__main__ import NoCamera

    detector, tray = build_detector("web", CATALOG, SimulatedScale(), {})
    assert isinstance(detector, NoCamera)
    assert tray is None
    assert detector.detect() == []


def test_build_recognizer_needs_a_gallery(tmp_path, monkeypatch):
    import kiosk.recognizer as rec
    from kiosk.__main__ import build_recognizer

    with pytest.raises(SystemExit, match="KIOSK_GALLERY"):
        build_recognizer({})
    with pytest.raises(SystemExit, match="KIOSK_GALLERY"):
        build_recognizer({"KIOSK_GALLERY": str(tmp_path / "no.npz")})
    gallery = tmp_path / "g.npz"
    gallery.write_bytes(b"x")
    seen = {}
    monkeypatch.setattr(
        rec.CropRecognizer,
        "from_files",
        classmethod(lambda cls, g, threshold, margin: seen.update(g=g, t=threshold, m=margin)),
    )
    # Sin variables: el reconocedor usa el umbral y el margen guardados en la galería
    build_recognizer({"KIOSK_GALLERY": str(gallery)})
    assert seen == {"g": gallery, "t": None, "m": None}
    build_recognizer({"KIOSK_GALLERY": str(gallery), "KIOSK_THRESHOLD": "1.3", "KIOSK_MARGIN": "0.08"})
    assert (seen["t"], seen["m"]) == (1.3, 0.08)
