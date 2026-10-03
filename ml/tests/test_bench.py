import numpy as np

from mltools.bench import letterbox, measure


class FakeClock:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t


def timed(clock: FakeClock, durations: list[float]):
    it = iter(durations)

    def fn() -> None:
        clock.t += next(it)

    return fn


def test_measure_stats_and_pass():
    clock = FakeClock()
    durations = [0.010] * 19 + [0.200]
    stats = measure(timed(clock, durations), runs=20, warmup=0, clock=clock)
    assert stats.p50_ms == 10.0
    assert stats.p95_ms == 10.0
    assert stats.mean_ms == 19.5
    assert stats.passes is True


def test_measure_fails_target():
    clock = FakeClock()
    stats = measure(timed(clock, [0.2] * 10), runs=10, warmup=0, clock=clock)
    assert stats.p95_ms == 200.0
    assert stats.passes is False


def test_warmup_runs_are_not_measured():
    clock = FakeClock()
    calls = []

    def fn() -> None:
        calls.append(1)
        clock.t += 1.0 if len(calls) <= 2 else 0.005

    stats = measure(fn, runs=5, warmup=2, clock=clock)
    assert len(calls) == 7
    assert stats.p95_ms == 5.0


def test_letterbox_shape_and_padding():
    image = np.zeros((720, 1280, 3), dtype=np.uint8)
    out = letterbox(image, 640)
    assert out.shape == (1, 3, 640, 640)
    assert out.dtype == np.float32
    assert abs(float(out[0, 0, 0, 320]) - 114 / 255) < 1e-6
    assert float(out[0, 0, 320, 320]) == 0.0
