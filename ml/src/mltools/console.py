import sys


def utf8_output() -> None:
    """Evita UnicodeEncodeError al imprimir ✅/❌/⚠️ en consolas Windows (cp1252)."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
