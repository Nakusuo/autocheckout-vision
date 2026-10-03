# autocheckout-vision

Quiosco de auto-checkout que reconoce productos con visión computacional (YOLOv8), valida el peso en una balanza y cobra con un QR.

- Requisitos: [`docs/SRS.md`](docs/SRS.md)
- Diseño aprobado: [`docs/superpowers/specs/2026-10-03-autocheckout-design.md`](docs/superpowers/specs/2026-10-03-autocheckout-design.md)

Licencia: AGPL-3.0 (ver `LICENSE`).

## Probar el sistema (simulado)

Requisitos: Python 3.12 y Node 22 o superior. En cada terminal Python define la misma clave:
`export GATEWAY_API_KEY=una-clave-larga-cualquiera` (ver `.env.example`).

```bash
# Terminal 1: pasarela de pago simulada (HTTPS :8443)
cd mock-gateway
python -m venv .venv && source .venv/Scripts/activate   # Linux/Mac: .venv/bin/activate
pip install -e ".[dev]"
python -m gateway.devkeys        # solo la primera vez: crea keys/ (fuera de git)
python -m gateway

# Terminal 2: API del quiosco (:8000)
cd kiosk-api
python -m venv .venv && source .venv/Scripts/activate
pip install -e ".[dev]"
python -m kiosk

# Terminal 3: interfaz (:5173)
cd kiosk-ui
npm install
npm run dev
```

| URL | Para qué |
|---|---|
| http://localhost:5173/ | Quiosco (cliente), formato vertical |
| http://localhost:5173/sim | Simulador: poner productos, esconder peso y abrir el «celular» que paga |
| http://localhost:5173/caja | Panel de caja: solicitudes de ayuda y reactivar el quiosco |

Para pagar: en la pantalla del QR, abre en `/sim` el enlace «Abrir el celular simulado» y pulsa «Pagar con Yape/Plin (simulado)». El quiosco consulta la pasarela por HTTPS (TLS 1.3), verifica la firma RS256 y muestra el ticket.

La API escucha en 127.0.0.1:8000 y solo acepta peticiones desde http://localhost:5173 (Vite usa ese puerto fijo; si está ocupado, libéralo).

## Herramientas del dataset (`ml/`)

```bash
cd ml
python -m venv .venv && source .venv/Scripts/activate
pip install -e ".[dev,bench]"

python -m mltools.dataset_check                 # revisa data/raw/ contra el catálogo
python -m mltools.frames VIDEO.mp4 --out data/raw/SKU   # fotos desde un video
python -m mltools.labelstudio                   # configuración para Label Studio
python -m mltools.bench --model modelo.onnx     # latencia vs RNF-01 (p95 ≤ 150 ms)
```

Guía de etiquetado: [`docs/ml/etiquetado.md`](docs/ml/etiquetado.md). Los datos (`ml/data/`) nunca van a git.
