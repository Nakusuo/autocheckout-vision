from pathlib import Path

import cv2
import numpy as np
import pytest

from kiosk.recognizer import (
    COLOR_WEIGHT,
    GRAY,
    UNKNOWN,
    Gallery,
    SimilarityDetector,
    build_gallery,
    color_hist,
    fingerprints,
    imread,
    isolate,
    leave_one_out,
)
from kiosk.tray import Detector
from kiosk.vision import ImageFolderSource

RED, BLUE, GREEN = (0, 0, 220), (220, 0, 0), (0, 200, 0)


def tray(color=None, size=(120, 160)) -> np.ndarray:
    """Bandeja blanca; con `color`, un producto rectangular en el centro."""
    img = np.full((*size, 3), 235, np.uint8)
    if color is not None:
        cv2.rectangle(img, (55, 35), (105, 85), color, -1)
    return img


def fake_embed(images: list[np.ndarray]) -> np.ndarray:
    """Huella de prueba: el color medio, normalizado (no necesita DINOv2)."""
    v = np.array([im.reshape(-1, 3).mean(axis=0) + 1 for im in images], np.float32)
    return v / np.linalg.norm(v, axis=1, keepdims=True)


def product_mask(img: np.ndarray) -> np.ndarray:
    return (np.abs(img.astype(int) - 235).sum(axis=2) > 30).astype(np.float32)


def test_isolate_crops_largest_blob_on_gray_square():
    img = tray(RED)
    crop, mask = isolate(img, product_mask(img))
    assert crop.shape[0] == crop.shape[1]
    assert tuple(crop[crop.shape[0] // 2, crop.shape[1] // 2]) == RED
    assert tuple(crop[0, 0]) == (GRAY,) * 3
    assert mask.sum() > 0


def test_isolate_without_product_returns_none():
    assert isolate(tray(), np.zeros((120, 160), np.float32)) is None


def test_color_hist_tells_colors_apart():
    def hist(color):
        crop, mask = isolate(tray(color), product_mask(tray(color)))
        return color_hist(crop, mask)

    assert float(hist(RED) @ hist(RED)) == pytest.approx(1.0)
    assert float(hist(RED) @ hist(BLUE)) < 0.1


def test_fingerprint_dot_product_adds_shape_and_color():
    crop, mask = isolate(tray(RED), product_mask(tray(RED)))
    fp = fingerprints(fake_embed, crop, mask, rotations=4)
    assert fp.shape[0] == 4
    assert float(fp[0] @ fp[0]) == pytest.approx(1 + COLOR_WEIGHT, rel=1e-5)


def gallery_of(*colors_by_sku: tuple[str, list]) -> Gallery:
    vectors, labels, photos = [], [], []
    for sku, colors in colors_by_sku:
        for color in colors:
            img = tray(color)
            fp = fingerprints(fake_embed, *isolate(img, product_mask(img)), rotations=4)
            vectors.append(fp)
            labels += [sku] * 4
            photos += [len(photos) // 4] * 4
    return Gallery(np.vstack(vectors), np.array(labels), np.array(photos))


def test_gallery_ranking_and_roundtrip(tmp_path: Path):
    gallery = gallery_of(("ROJO", [RED, RED]), ("AZUL", [BLUE, BLUE]))
    path = tmp_path / "g.npz"
    gallery.save(path)
    loaded = Gallery.load(path)

    query = loaded.vectors[0]
    assert loaded.ranking(query)[0][0] == "ROJO"
    assert [sku for sku, _ in loaded.ranking(query)] == ["ROJO", "AZUL"]


def test_leave_one_out_skips_the_photo_itself():
    hits, total, misses = leave_one_out(gallery_of(("ROJO", [RED, RED]), ("AZUL", [BLUE])))
    assert (hits, total) == (2, 3)  # AZUL no tiene otra foto con qué compararse
    assert misses[0][:2] == ("AZUL", "ROJO")


def test_build_gallery_reads_catalog_folders(tmp_path: Path):
    for sku, color in (("ROJO", RED), ("AZUL", BLUE), ("OTRO", GREEN)):
        (tmp_path / sku).mkdir()
        cv2.imencode(".png", tray(color))[1].tofile(tmp_path / sku / "a.png")
    gallery = build_gallery(tmp_path, fake_embed, product_mask, skus={"ROJO", "AZUL"})
    assert sorted(set(gallery.labels)) == ["AZUL", "ROJO"]
    assert len(gallery.vectors) == 8
    assert imread(tmp_path / "ROJO" / "a.png").shape == (120, 160, 3)


def detector(frames: list[np.ndarray], threshold: float = 1.2) -> SimilarityDetector:
    gallery = gallery_of(("ROJO", [RED]), ("AZUL", [BLUE]))
    return SimilarityDetector(
        fake_embed, gallery, ImageFolderSource(frames), threshold=threshold, warmup_frames=2
    )


def test_similarity_detector_is_a_detector():
    assert isinstance(detector([tray()]), Detector)


def test_detects_one_product_after_learning_the_empty_tray():
    d = detector([tray(), tray(), tray(), tray(BLUE), tray(RED), tray()])
    assert [d.detect() for _ in range(6)] == [[], [], [], ["AZUL"], ["ROJO"], []]


def test_low_similarity_is_unknown():
    d = detector([tray(), tray(), tray(GREEN)])
    assert [d.detect() for _ in range(3)] == [[], [], [UNKNOWN]]
    assert d.last is not None


def two_products() -> np.ndarray:
    img = tray()
    cv2.rectangle(img, (5, 5), (40, 40), RED, -1)
    cv2.rectangle(img, (115, 75), (150, 110), BLUE, -1)
    return img


def test_two_products_in_view_are_not_guessed():
    d = detector([tray(), tray(), two_products()])
    assert [d.detect() for _ in range(3)] == [[], [], [UNKNOWN]]


def small_product() -> np.ndarray:
    img = tray()
    cv2.rectangle(img, (70, 50), (79, 59), RED, -1)  # 100 px: 0,5 % de la imagen
    return img


def test_small_product_is_seen_and_never_absorbed_into_the_background():
    d = detector([tray(), tray()] + [small_product()] * 30)
    results = [d.detect() for _ in range(32)]
    assert results[2] != []
    assert results[-1] == results[2]  # sigue a la vista: el fondo no se lo «tragó»


def test_background_learning_skips_the_foreground():
    from kiosk.recognizer import BackgroundModel

    bg = BackgroundModel(learn_rate=1.0)
    bg.learn(tray())
    fg = bg.foreground(small_product())
    bg.learn(small_product(), fg)
    assert bg.foreground(small_product()).sum() > 0


def test_recalibrate_learns_the_current_view_as_background():
    d = detector([tray(), tray()] + [tray(BLUE)] * 10)
    assert [d.detect() for _ in range(3)] == [[], [], ["AZUL"]]
    d.recalibrate()
    assert [d.detect() for _ in range(3)] == [[], [], []]  # lo que había quedó como fondo
