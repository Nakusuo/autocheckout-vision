"""Arranque en la nube (Cloud Run): baja los archivos privados y lanza el quiosco.

Los modelos (DINOv2, galería del recuadro) y el QR de Yape no están en git: viven en un
repositorio **privado** de Hugging Face (HF_MODELOS, p. ej. «usuario/autocaja-modelos») y se bajan
con el secreto HF_TOKEN (solo lectura). Si ya están en disco (prueba local), no baja nada.

Cloud Run da el puerto en PORT. La API acepta su propia dirección https sin configurarla y no
arranca sin la clave de caja (KIOSK_CAJA_KEY): ver kiosk/__main__.py, cloud_settings.
"""

import os
import sys
from pathlib import Path

MODELS = Path("/app/ml/data/models")


def needed(env: dict[str, str]) -> dict[str, Path]:
    """Archivo del repo privado → dónde lo busca el quiosco (KIOSK_GALLERY, KIOSK_YAPE_QR)."""
    return {
        "dinov2-small.onnx": MODELS / "dinov2-small.onnx",
        "galeria-recuadro.npz": Path(env.get("KIOSK_GALLERY") or MODELS / "galeria-recuadro.npz"),
        "yape-qr.png": Path(env.get("KIOSK_YAPE_QR") or MODELS / "yape-qr.png"),
    }


def download(env: dict[str, str]) -> None:
    """Baja de HF_MODELOS (a MODELS) los archivos que falten."""
    missing = [name for name, path in needed(env).items() if not path.is_file()]
    if not missing:
        return
    repo = env.get("HF_MODELOS")
    if not repo:
        sys.exit(f"Faltan {', '.join(missing)} y no está HF_MODELOS (repo privado de modelos)")
    from huggingface_hub import hf_hub_download

    for name in missing:
        hf_hub_download(repo, name, token=env.get("HF_TOKEN"), local_dir=MODELS)
        print(f"Bajado {name} de {repo}", flush=True)


def main() -> None:
    """Prepara el entorno y reemplaza este proceso por `python -m kiosk`."""
    env = dict(os.environ)
    download(env)
    if env.get("PORT"):
        os.environ["KIOSK_PORT"] = env["PORT"]
    os.execvp(sys.executable, [sys.executable, "-m", "kiosk"])  # nosec B606: sin shell, fijo


if __name__ == "__main__":
    main()
