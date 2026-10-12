"""Arranque del servidor y comandos de línea, sin cámara, modelos ONNX ni red."""

from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
import pytest
from payment_helpers import PUBLIC_PEM
from test_recognizer import BLUE, RED, fake_embed, product_mask, tray

import kiosk.__main__ as entry
import kiosk.recognizer as rec
from kiosk import vision
from kiosk.recognizer import Embedder, Gallery, Segmenter, SimilarityDetector
from kiosk.vision import ImageFolderSource

# ---------- kiosk.__main__.main ----------


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """Un repositorio mínimo: claves, catálogo y carpeta kiosk-api."""
    (tmp_path / "keys").mkdir()
    (tmp_path / "keys" / "gateway_jwt_public.pem").write_bytes(PUBLIC_PEM)
    (tmp_path / "keys" / "ca.pem").write_text("ca")
    (tmp_path / "catalog").mkdir()
    (tmp_path / "catalog" / "products.csv").write_text(
        "sku,name,price_cents,weight_g\nAGUA,Agua,250,651.0\n", encoding="utf-8"
    )
    (tmp_path / "kiosk-api").mkdir()
    monkeypatch.setattr(entry, "REPO", tmp_path)
    monkeypatch.setattr(entry, "HttpGateway", lambda *a, **k: SimpleNamespace())
    started = {}
    monkeypatch.setattr(entry.uvicorn, "run", lambda app, **kw: started.update(app=app, **kw))
    monkeypatch.setenv("GATEWAY_API_KEY", "clave")
    monkeypatch.delenv("KIOSK_MODE", raising=False)
    monkeypatch.delenv("KIOSK_SCALE", raising=False)
    return tmp_path, started


def test_main_starts_sim_kiosk_on_localhost(repo):
    root, started = repo
    entry.main()
    assert started["host"] == "127.0.0.1" and started["port"] == 8000
    paths = {r.path for r in started["app"].routes}
    assert "/sim/scan" in paths and "/api/state" in paths
    assert (root / "kiosk-api" / "kiosk.db").exists()


def test_main_without_api_key_exits(repo, monkeypatch):
    monkeypatch.delenv("GATEWAY_API_KEY")
    with pytest.raises(SystemExit, match="GATEWAY_API_KEY"):
        entry.main()


def test_main_without_keys_exits(repo):
    root, _ = repo
    (root / "keys" / "ca.pem").unlink()
    with pytest.raises(SystemExit, match="devkeys"):
        entry.main()


def test_main_camera_mode_with_simulated_scale_warns_and_has_no_sim_routes(
    repo, monkeypatch, caplog
):
    _, started = repo
    fake_camera = SimpleNamespace(detect=list)
    monkeypatch.setattr(entry, "build_detector", lambda *a: (fake_camera, None))
    monkeypatch.setenv("KIOSK_MODE", "camera")
    monkeypatch.setenv("KIOSK_SCALE", "sim")
    entry.main()
    assert "no valida nada" in caplog.text
    assert "/sim/scan" not in {r.path for r in started["app"].routes}


def test_build_detector_camera_with_gallery_uses_similarity(monkeypatch, tmp_path):
    monkeypatch.setattr(vision, "CameraSource", lambda index: ImageFolderSource([tray()]))
    monkeypatch.setattr(
        rec.SimilarityDetector, "from_files", classmethod(lambda cls, g, s, **kw: ("similar", kw))
    )
    detector, tray_ = entry.build_detector(
        "camera", None, None, {"KIOSK_GALLERY": str(tmp_path / "g.npz"), "KIOSK_THRESHOLD": "1.1"}
    )
    assert detector == ("similar", {"threshold": 1.1, "zone": None, "hands": True})
    assert tray_ is None


def test_build_detector_camera_with_zone_and_without_hand_filter(monkeypatch, tmp_path):
    monkeypatch.setattr(vision, "CameraSource", lambda index: ImageFolderSource([tray()]))
    monkeypatch.setattr(
        rec.SimilarityDetector, "from_files", classmethod(lambda cls, g, s, **kw: kw)
    )
    env = {
        "KIOSK_GALLERY": str(tmp_path / "g.npz"),
        "KIOSK_ZONE": "0.25,0.1,0.75,0.9",
        "KIOSK_HANDS": "off",
    }
    kw, _ = entry.build_detector("camera", None, None, env)
    assert (kw["zone"], kw["hands"]) == ((0.25, 0.1, 0.75, 0.9), False)
    with pytest.raises(ValueError, match="Zona inválida"):
        entry.build_detector("camera", None, None, {**env, "KIOSK_ZONE": "1,1,0,0"})


def test_build_detector_camera_with_yolo_model(monkeypatch, tmp_path):
    monkeypatch.setattr(vision, "CameraSource", lambda index: ImageFolderSource([tray()]))
    monkeypatch.setattr(
        vision.YoloOnnxDetector, "from_model", classmethod(lambda cls, m, s, imgsz: ("yolo", imgsz))
    )
    detector, _ = entry.build_detector("camera", None, None, {"KIOSK_MODEL": "m.onnx"})
    assert detector == ("yolo", 416)


# ---------- kiosk.recognizer: modelos con sesiones falsas ----------


class FakeSession:
    def __init__(self, output):
        self._output = output
        self.fed = None

    def get_inputs(self):
        return [SimpleNamespace(name="entrada")]

    def run(self, _names, feed):
        self.fed = feed["entrada"]
        return [self._output(self.fed)]


def test_embedder_returns_normalized_cls_token_at_its_size():
    session = FakeSession(lambda x: np.ones((x.shape[0], 5, 3), np.float32))
    embed = Embedder(session, size=28)
    out = embed([tray(RED), tray(BLUE)])
    assert session.fed.shape == (2, 3, 28, 28)
    assert out.shape == (2, 3)
    assert np.allclose(np.linalg.norm(out, axis=1), 1.0)


def test_segmenter_rescales_mask_to_frame_size():
    session = FakeSession(lambda x: np.linspace(0, 5, 320 * 320).reshape(1, 1, 320, 320))
    mask = Segmenter(session)(tray(RED))
    assert mask.shape == (120, 160)
    assert mask.min() == pytest.approx(0, abs=0.01) and mask.max() == pytest.approx(1, abs=0.01)


# ---------- kiosk.recognizer.main (CLI) ----------


@pytest.fixture
def fake_models(monkeypatch):
    """Embedder y segmentador de prueba; la cámara entrega una bandeja con un producto."""
    monkeypatch.setattr(rec.Embedder, "from_model", classmethod(lambda cls, *a: _FakeEmbed()))
    monkeypatch.setattr(rec.Segmenter, "from_model", classmethod(lambda cls, *a: product_mask))
    monkeypatch.setattr(
        rec, "CameraSource", lambda index: _Camera([tray()] * 12 + [tray(RED)] * 40)
    )
    monkeypatch.setattr(rec.time, "sleep", lambda s: None)


class _FakeEmbed:
    size = 140

    def __call__(self, images):
        return fake_embed(images)


class _Camera(ImageFolderSource):
    closed = False

    def close(self):
        self.closed = True


def photos(raw: Path) -> Path:
    for sku, color in (("ROJO", RED), ("AZUL", BLUE)):
        for i in range(2):
            (raw / sku).mkdir(parents=True, exist_ok=True)
            cv2.imencode(".png", tray(color))[1].tofile(raw / sku / f"{i}.png")
    catalog = raw.parent / "products.csv"
    catalog.write_text(
        "sku,name,price_cents,weight_g\nROJO,Rojo,100,10\nAZUL,Azul,100,10\nVERDE,Verde,100,10\n",
        encoding="utf-8",
    )
    return catalog


def test_cli_gallery_then_evaluate(tmp_path, fake_models, capsys):
    raw, gallery = tmp_path / "raw", tmp_path / "g.npz"
    catalog = photos(raw)
    assert (
        rec.main(
            ["--galeria", str(gallery), "galeria", "--raw", str(raw), "--catalogo", str(catalog)]
        )
        == 0
    )
    out = capsys.readouterr().out
    assert "4 fotos de 2 productos" in out
    assert "Sin fotos (no se podrán reconocer): VERDE" in out
    assert Gallery.load(gallery).size == 140

    assert rec.main(["--galeria", str(gallery), "evaluar"]) == 0
    assert "4/4 = 100%" in capsys.readouterr().out


def test_cli_evaluate_lists_misses(tmp_path, capsys):
    g = Gallery(
        np.array([[1.0, 0.0], [0.9, 0.1], [0.0, 1.0]], np.float32),
        np.array(["A", "B", "B"]),
        np.array([0, 1, 2]),
    )
    g.save(tmp_path / "g.npz")
    rec.main(["--galeria", str(tmp_path / "g.npz"), "evaluar"])
    out = capsys.readouterr().out
    assert "A → B" in out


def test_cli_benchmark_reports_against_rnf01(tmp_path, fake_models, capsys):
    raw, gallery = tmp_path / "raw", tmp_path / "g.npz"
    rec.main(
        ["--galeria", str(gallery), "galeria", "--raw", str(raw), "--catalogo", str(photos(raw))]
    )
    assert rec.main(["--galeria", str(gallery), "medir", "--raw", str(raw), "--cuadros", "5"]) == 0
    assert "RNF-01" in capsys.readouterr().out


def test_cli_benchmark_without_photos_fails(tmp_path, fake_models, capsys):
    (tmp_path / "raw").mkdir()
    assert rec.main(["medir", "--raw", str(tmp_path / "raw")]) == 1
    assert "No hay fotos" in capsys.readouterr().out


def test_cli_capture_saves_photos_in_sku_folder(tmp_path, fake_models):
    raw = tmp_path / "raw"
    assert rec.main(["capturar", "ROJO", "--fotos", "3", "--raw", str(raw)]) == 0
    saved = sorted((raw / "ROJO").glob("CAM_*.jpg"))
    assert len(saved) == 3
    assert rec.imread(saved[0]).shape == (120, 160, 3)


def test_cli_live_camera_prints_best_match_and_closes(tmp_path, fake_models, capsys):
    raw, gallery = tmp_path / "raw", tmp_path / "g.npz"
    rec.main(
        ["--galeria", str(gallery), "galeria", "--raw", str(raw), "--catalogo", str(photos(raw))]
    )
    assert rec.main(["--galeria", str(gallery), "camara", "--frames", "15"]) == 0
    out = capsys.readouterr().out
    assert "['ROJO']" in out and "mejor: ROJO" in out


def test_similarity_detector_from_files_uses_gallery_size(tmp_path, monkeypatch):
    sizes = []
    monkeypatch.setattr(
        rec.Embedder,
        "from_model",
        classmethod(lambda cls, path, size: sizes.append(size) or _FakeEmbed()),
    )
    Gallery(np.zeros((1, 2), np.float32), np.array(["A"]), np.array([0]), size=112).save(
        tmp_path / "g.npz"
    )
    SimilarityDetector.from_files(tmp_path / "g.npz", ImageFolderSource([tray()]))
    assert sizes == [112]


# ---------- kiosk.vision.main ----------


def test_vision_cli_prints_each_frame(monkeypatch, capsys):
    camera = _Camera([tray()])
    monkeypatch.setattr(vision, "CameraSource", lambda index: camera)
    monkeypatch.setattr(
        vision.YoloOnnxDetector,
        "from_model",
        classmethod(lambda cls, m, s, imgsz: SimpleNamespace(detect=lambda: ["AGUA"])),
    )
    assert vision.main(["--model", "m.onnx", "--frames", "2"]) == 0
    assert capsys.readouterr().out.count("['AGUA']") == 2
    assert camera.closed


def test_vision_cli_without_camera_fails(monkeypatch, capsys):
    def no_camera(index):
        raise OSError("No se pudo abrir la cámara 0")

    monkeypatch.setattr(vision, "CameraSource", no_camera)
    assert vision.main(["--model", "m.onnx"]) == 1
    assert "No se pudo abrir" in capsys.readouterr().out


def test_cli_zone_saves_a_photo_with_the_rectangle(tmp_path, fake_models, capsys):
    out = tmp_path / "zona.jpg"
    assert rec.main(["zona", "0.25,0.25,0.75,0.75", "--salida", str(out)]) == 0
    assert tuple(rec.imread(out)[30, 80]) != (235, 235, 235)  # el recuadro se dibujó
    assert "KIOSK_ZONE=0.25,0.25,0.75,0.75" in capsys.readouterr().out


def test_cli_live_camera_with_zone(tmp_path, fake_models, capsys):
    raw, gallery = tmp_path / "raw", tmp_path / "g.npz"
    rec.main(
        ["--galeria", str(gallery), "galeria", "--raw", str(raw), "--catalogo", str(photos(raw))]
    )
    args = ["--galeria", str(gallery), "camara", "--frames", "15", "--zona", "0,0,1,1"]
    assert rec.main(args) == 0
    assert "['ROJO']" in capsys.readouterr().out
