from pathlib import Path

import pytest

from gateway.__main__ import DEFAULT_PUBLIC_URL, load_settings

BASE = {"GATEWAY_API_KEY": "clave"}


def keys_dir(tmp_path: Path, *names: str) -> Path:
    for name in names:
        (tmp_path / name).write_text("x")
    return tmp_path


def test_defaults_are_local_with_tls(tmp_path):
    keys = keys_dir(tmp_path, "gateway_jwt_private.pem", "server.pem", "server-key.pem")
    s = load_settings({**BASE, "GATEWAY_KEYS_DIR": str(keys)})
    assert (s.host, s.port, s.tls) == ("127.0.0.1", 8443, True)
    assert s.public_url == DEFAULT_PUBLIC_URL
    assert s.keys == keys


def test_cloud_mode_without_tls_reads_paas_port_and_url(tmp_path):
    keys = keys_dir(tmp_path, "gateway_jwt_private.pem")
    env = {
        **BASE,
        "GATEWAY_KEYS_DIR": str(keys),
        "GATEWAY_TLS": "off",
        "GATEWAY_HOST": "0.0.0.0",
        "PORT": "10000",
        "RENDER_EXTERNAL_URL": "https://autocaja-pasarela.onrender.com/",
    }
    s = load_settings(env)
    assert (s.host, s.port, s.tls) == ("0.0.0.0", 10000, False)
    assert s.public_url == "https://autocaja-pasarela.onrender.com"


def test_explicit_values_win_over_paas_ones(tmp_path):
    keys = keys_dir(tmp_path, "gateway_jwt_private.pem")
    env = {
        **BASE,
        "GATEWAY_KEYS_DIR": str(keys),
        "GATEWAY_TLS": "off",
        "GATEWAY_PORT": "8443",
        "PORT": "10000",
        "GATEWAY_PUBLIC_URL": "https://pago.example",
        "RENDER_EXTERNAL_URL": "https://otro.example",
    }
    s = load_settings(env)
    assert s.port == 8443
    assert s.public_url == "https://pago.example"


def test_default_keys_dir_is_repo_keys(tmp_path, monkeypatch):
    monkeypatch.setattr("gateway.__main__.REPO", tmp_path)
    (tmp_path / "keys").mkdir()
    keys_dir(tmp_path / "keys", "gateway_jwt_private.pem")
    assert load_settings({**BASE, "GATEWAY_TLS": "off"}).keys == tmp_path / "keys"


def test_missing_api_key_exits():
    with pytest.raises(SystemExit, match="GATEWAY_API_KEY"):
        load_settings({})


def test_unknown_tls_mode_exits():
    with pytest.raises(SystemExit, match="GATEWAY_TLS"):
        load_settings({**BASE, "GATEWAY_TLS": "quizas"})


@pytest.mark.parametrize("port", ["abc", "0", "70000"])
def test_invalid_port_exits(port):
    with pytest.raises(SystemExit, match="Puerto"):
        load_settings({**BASE, "GATEWAY_PORT": port})


def test_missing_tls_files_are_listed(tmp_path):
    keys = keys_dir(tmp_path, "gateway_jwt_private.pem")
    with pytest.raises(SystemExit, match="server.pem, server-key.pem"):
        load_settings({**BASE, "GATEWAY_KEYS_DIR": str(keys)})


def test_without_tls_only_the_signing_key_is_needed(tmp_path):
    with pytest.raises(SystemExit, match="gateway_jwt_private.pem"):
        load_settings({**BASE, "GATEWAY_KEYS_DIR": str(tmp_path), "GATEWAY_TLS": "off"})
