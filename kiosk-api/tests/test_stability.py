from kiosk.stability import StabilityFilter


def test_needs_three_equal_frames():
    f = StabilityFilter()
    assert f.push(["B", "A"]) is None
    assert f.push(["A", "B"]) is None
    assert f.push(["B", "A"]) == ["A", "B"]


def test_change_restarts_count():
    f = StabilityFilter()
    f.push(["A"])
    f.push(["A"])
    assert f.push(["A", "A"]) is None
    assert f.push(["A", "A"]) is None
    assert f.push(["A", "A"]) == ["A", "A"]


def test_empty_tray_is_stable_too():
    f = StabilityFilter(frames_required=2)
    f.push([])
    assert f.push([]) == []


def test_reset_forgets_history():
    f = StabilityFilter(frames_required=2)
    f.push(["A"])
    f.reset()
    assert f.push(["A"]) is None
