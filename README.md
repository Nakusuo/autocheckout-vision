# autocheckout-vision

Quiosco de auto-checkout que reconoce productos con visión computacional (YOLOv8), valida el peso en una balanza y cobra con un QR.

- Requisitos: [`docs/SRS.md`](docs/SRS.md)
- Diseño aprobado: [`docs/superpowers/specs/2026-10-03-autocheckout-design.md`](docs/superpowers/specs/2026-10-03-autocheckout-design.md)

Licencia: AGPL-3.0 (ver `LICENSE`).

## Probar el sistema (simulado)

Requisitos: Python 3.12 y Node 22 o superior.

```bash
# Terminal 1: API del quiosco
cd kiosk-api
python -m venv .venv && source .venv/Scripts/activate   # Linux/Mac: .venv/bin/activate
pip install -e ".[dev]"
python -m kiosk

# Terminal 2: interfaz
cd kiosk-ui
npm install
npm run dev
```

| URL | Para qué |
|---|---|
| http://localhost:5173/ | Quiosco (cliente), formato vertical |
| http://localhost:5173/sim | Simulador: poner productos en la bandeja, esconder peso, simular el pago |
| http://localhost:5173/caja | Panel de caja: solicitudes de ayuda y reactivar el quiosco |

La API escucha en 127.0.0.1:8000 y solo acepta peticiones desde http://localhost:5173 (Vite usa ese puerto fijo; si está ocupado, libéralo).
