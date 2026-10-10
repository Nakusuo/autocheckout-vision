from pathlib import Path

from mltools.train import AUGMENT, evaluate_gate, main


def test_gate_passes_above_target():
    ok, message = evaluate_gate(0.934)
    assert ok is True
    assert "0.934" in message and "CUMPLE" in message


def test_gate_exact_target_passes():
    assert evaluate_gate(0.90)[0] is True


def test_gate_fails_below_target():
    ok, message = evaluate_gate(0.81)
    assert ok is False and "NO CUMPLE" in message


def test_overhead_augmentations_rotate_but_never_mirror():
    assert AUGMENT["degrees"] == 180.0
    assert AUGMENT["fliplr"] == 0.0 and AUGMENT["flipud"] == 0.0


def test_main_without_dataset_returns_1(tmp_path: Path, capsys):
    assert main(["--data", str(tmp_path / "no-existe.yaml")]) == 1
    assert "mltools.split" in capsys.readouterr().out
