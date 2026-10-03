import io
import sys

from mltools.console import utf8_output


def test_utf8_output_on_cp1252_console(monkeypatch):
    """UTF-8 output should not raise UnicodeEncodeError on Windows cp1252 console."""
    # Simulate a Windows console with cp1252 encoding
    fake_stdout = io.TextIOWrapper(io.BytesIO(), encoding="cp1252")
    monkeypatch.setattr(sys, "stdout", fake_stdout)

    # This should not raise UnicodeEncodeError
    utf8_output()
    print("❌ ✅")
