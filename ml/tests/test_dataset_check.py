from pathlib import Path

from mltools.catalog import REPO, load_skus
from mltools.dataset_check import check_dataset, format_report

SKUS = {"AGUA", "COLA", "TAKIS"}


def put(root: Path, rel: str, content: bytes | None = None) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content if content is not None else rel.encode())


def test_counts_and_ok(tmp_path: Path):
    for i in range(3):
        put(tmp_path, f"AGUA/a_{i}.jpg")
    put(tmp_path, "COLA/c_1.PNG")
    put(tmp_path, "mezclas/m_1.jpeg")
    put(tmp_path, "videos/v_1.mp4")

    report = check_dataset(tmp_path, SKUS, min_per_product=2)

    assert report.counts == {"AGUA": 3, "COLA": 1, "mezclas": 1, "videos": 1}
    assert report.missing_skus == ["TAKIS"]
    assert report.low_skus == ["COLA"]
    assert report.ok is True


def test_unknown_folder_fails(tmp_path: Path):
    put(tmp_path, "Coca Cola/x.jpg")
    report = check_dataset(tmp_path, SKUS)
    assert report.unknown_folders == ["Coca Cola"]
    assert report.ok is False


def test_bad_extensions_fail(tmp_path: Path):
    put(tmp_path, "AGUA/nota.txt")
    put(tmp_path, "AGUA/clip.mp4")
    put(tmp_path, "videos/foto.jpg")
    report = check_dataset(tmp_path, SKUS)
    assert sorted(report.bad_files) == ["AGUA/clip.mp4", "AGUA/nota.txt", "videos/foto.jpg"]
    assert report.ok is False


def test_duplicates_counted_once(tmp_path: Path):
    put(tmp_path, "AGUA/a.jpg", b"misma")
    put(tmp_path, "AGUA/b.jpg", b"misma")
    report = check_dataset(tmp_path, SKUS)
    assert report.counts["AGUA"] == 1
    assert report.duplicates == [("AGUA/a.jpg", "AGUA/b.jpg")]
    assert report.ok is True


def test_system_files_ignored(tmp_path: Path):
    put(tmp_path, "AGUA/desktop.ini")
    put(tmp_path, "AGUA/Thumbs.db")
    report = check_dataset(tmp_path, SKUS)
    assert report.counts["AGUA"] == 0
    assert report.bad_files == []


def test_format_report_marks_states(tmp_path: Path):
    put(tmp_path, "AGUA/a.jpg")
    text = format_report(check_dataset(tmp_path, SKUS, min_per_product=5))
    assert "AGUA" in text and "pocas" in text
    assert "TAKIS" in text and "falta" in text


def test_load_skus_from_repo_catalog():
    skus = load_skus(REPO / "catalog" / "products.csv")
    assert skus and all(s == s.upper() for s in skus)
