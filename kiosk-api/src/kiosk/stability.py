from collections import Counter


class StabilityFilter:
    """Da por buena una detección cuando se repite igual en N cuadros seguidos."""

    def __init__(self, frames_required: int = 3):
        self._required = frames_required
        self._last: Counter[str] | None = None
        self._count = 0

    def push(self, skus: list[str]) -> list[str] | None:
        current = Counter(skus)
        if current == self._last:
            self._count += 1
        else:
            self._last = current
            self._count = 1
        if self._count >= self._required:
            return sorted(current.elements())
        return None

    def reset(self) -> None:
        self._last = None
        self._count = 0
