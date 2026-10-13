from kiosk.scale import ScaleReader, SimulatedScale


def test_without_noise_reads_exact_load():
    s = SimulatedScale(noise_g=0)
    s.set_load(684.0)
    assert s.read() == 684.0


def test_noise_stays_within_bounds():
    s = SimulatedScale(noise_g=2.0, seed=42)
    s.set_load(500.0)
    readings = [s.read() for _ in range(1000)]
    assert all(498.0 <= r <= 502.0 for r in readings)
    assert min(readings) < 499.0 and max(readings) > 501.0  # hay ruido de verdad, no un valor fijo


def test_trap_adds_hidden_weight():
    s = SimulatedScale(noise_g=0)
    s.set_load(100.0)
    s.set_trap(40.0)
    assert s.read() == 140.0


def test_never_negative():
    s = SimulatedScale(noise_g=2.0, seed=1)
    assert all(s.read() >= 0.0 for _ in range(100))


def test_satisfies_scale_reader_protocol():
    assert isinstance(SimulatedScale(), ScaleReader)
