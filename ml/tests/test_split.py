from pathlib import Path

import pytest

from mltools.split import build_dataset, split_names

SKUS = {"AGUA", "COLA", "TAKIS"}


def make_export(root: Path, n: int = 10, classes=("AGUA", "COLA"), label="0 0.5 0.5 0.2 0.2") -> Path:
    (root / "images").mkdir(parents=True)
    (root / "labels").mkdir()
    (root / "classes.txt").write_text("\n".join(classes) + "\n", encoding="utf-8")
    for i in range(n):
        (root / "images" / f"foto_{i:02d}.jpg").write_bytes(b"jpg")
        (root / "labels" / f"foto_{i:02d}.txt").write_text(label + "\n", encoding="utf-8")
    return root


def test_split_names_is_deterministic_70_20_10():
    names = [f"f{i}" for i in range(10)]
    a = split_names(names, seed=7)
    assert a == split_names(list(reversed(names)), seed=7)
    assert [len(a[k]) for k in ("train", "val", "test")] == [7, 2, 1]
    assert sorted(a["train"] + a["val"] + a["test"]) == sorted(names)


def test_build_dataset_writes_splits_and_yaml(tmp_path: Path):
    export = make_export(tmp_path / "export")
    yaml = build_dataset(export, tmp_path / "dataset", SKUS)

    text = yaml.read_text(encoding="utf-8")
    assert "train: images/train" in text and "test: images/test" in text
    assert "  0: AGUA" in text and "  1: COLA" in text
    counts = [len(list((tmp_path / "dataset" / "images" / s).iterdir())) for s in ("train", "val", "test")]
    assert counts == [7, 2, 1]
    assert len(list((tmp_path / "dataset" / "labels" / "train").iterdir())) == 7


def test_unknown_class_is_rejected(tmp_path: Path):
    export = make_export(tmp_path / "export", classes=("AGUA", "PEPSI"))
    with pytest.raises(ValueError, match="catálogo"):
        build_dataset(export, tmp_path / "dataset", SKUS)


def test_missing_label_is_rejected(tmp_path: Path):
    export = make_export(tmp_path / "export")
    (export / "labels" / "foto_03.txt").unlink()
    with pytest.raises(ValueError, match="sin etiquetas"):
        build_dataset(export, tmp_path / "dataset", SKUS)


@pytest.mark.parametrize("label", ["5 0.5 0.5 0.2 0.2", "0 0.5 0.5 1.2 0.2", "0 0.5 0.5"])
def test_bad_label_lines_are_rejected(tmp_path: Path, label: str):
    export = make_export(tmp_path / "export", label=label)
    with pytest.raises(ValueError, match="etiqueta inválida"):
        build_dataset(export, tmp_path / "dataset", SKUS)


def test_output_folder_is_protected(tmp_path: Path):
    export = make_export(tmp_path / "export")
    out = tmp_path / "dataset"
    out.mkdir()
    (out / "importante.txt").write_text("no borrar", encoding="utf-8")
    with pytest.raises(ValueError, match="no fue generada"):
        build_dataset(export, out, SKUS)
    assert (out / "importante.txt").exists()

    (out / "importante.txt").unlink()
    build_dataset(export, out, SKUS)
    build_dataset(export, out, SKUS)  # una segunda vez la reemplaza sin error
    assert (out / "data.yaml").exists()
