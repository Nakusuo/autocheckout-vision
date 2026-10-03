from pathlib import Path

import cv2
import numpy as np
import pytest

from mltools.frames import extract_frames

FPS = 10


def make_video(path: Path, colors: list[int], frames_each: int = 20) -> Path:
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), FPS, (64, 64))
    for value in colors:
        for _ in range(frames_each):
            writer.write(np.full((64, 64, 3), value, dtype=np.uint8))
    writer.release()
    return path


def test_keeps_only_changes(tmp_path: Path):
    video = make_video(tmp_path / "v.avi", [0, 255, 0])
    saved = extract_frames(video, tmp_path / "out", every_s=0.5)
    assert saved == 3
    assert sorted(p.name for p in (tmp_path / "out").iterdir()) == [
        "v_0000.jpg",
        "v_0001.jpg",
        "v_0002.jpg",
    ]


def test_min_diff_zero_keeps_every_sample(tmp_path: Path):
    video = make_video(tmp_path / "v.avi", [0, 255, 0])
    assert extract_frames(video, tmp_path / "out", every_s=0.5, min_diff=0.0) == 12


def test_custom_prefix(tmp_path: Path):
    video = make_video(tmp_path / "v.avi", [0])
    extract_frames(video, tmp_path / "out", prefix="JP_cola")
    assert (tmp_path / "out" / "JP_cola_0000.jpg").exists()


def test_unreadable_video_raises(tmp_path: Path):
    with pytest.raises(ValueError, match="No se pudo abrir"):
        extract_frames(tmp_path / "no-existe.mp4", tmp_path / "out")
