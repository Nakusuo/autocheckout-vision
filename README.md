# autocheckout-vision

Quiosco de auto-checkout que reconoce productos con visión computacional (por parecido con una galería de fotos; YOLOv8 cuando haya dataset), opcionalmente valida el peso en una balanza y cobra con un QR.

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
| http://localhost:5173/sim | Simulador para la presentación: pasar cada producto por la cámara (o ponerlo «sin escanear»), escenarios paso a paso, balanza, acciones del quiosco, enlace al «celular» que paga y vista en vivo del quiosco |
| http://localhost:5173/caja | Panel de caja: solicitudes de ayuda y reactivar el quiosco |

Para pagar: en la pantalla del QR, abre en `/sim` el enlace «Abrir el celular simulado» y pulsa «Pagar con Yape/Plin (simulado)». El quiosco consulta la pasarela por HTTPS (TLS 1.3), verifica la firma RS256 y muestra el ticket.

La API escucha en 127.0.0.1:8000 y solo acepta peticiones desde http://localhost:5173 (Vite usa ese puerto fijo; si está ocupado, libéralo).

**Balanza:** por defecto no se usa (`KIOSK_SCALE=off`): el quiosco cobra lo que reconoce la cámara. Con `KIOSK_SCALE=sim` se activa la balanza simulada y la validación de peso (±5 g, ON-02), con la trampa de peso en `/sim`.

Cada venta pagada emite una boleta simulada del POS (serie `B001`) que se guarda en `kiosk-api/boletas.jsonl` (fuera de git).

Cada compra queda registrada en `kiosk-api/sesiones.jsonl` (duración de INICIAR a W4, ayuda pedida, alertas de peso). `python -m kiosk.metrics` en `kiosk-api` resume esos datos frente a las metas del SRS (ON-01/02/03, RNF-02); se usa en la demo, ver [`docs/superpowers/plans/2026-10-10-m5-demo.md`](docs/superpowers/plans/2026-10-10-m5-demo.md).

### Pruebas de punta a punta (Playwright)

Recorren W1 a W4 con los tres servicios reales en modo simulado: trampa de peso, CORREGIR, pago desde el «celular», ticket, boleta y vuelta a W1, más SOLICITAR AYUDA en el panel de caja. Levantan solos la pasarela, la API y el build de la UI (usan el `.venv` de cada servicio si existe).

```bash
cd kiosk-ui
npx playwright install chromium   # solo la primera vez
npm run e2e
```

Si ya tienes los servicios abiertos, las pruebas los reutilizan; el quiosco debe estar en W1.

## Modo cámara

Requiere el extra de visión: `pip install -e ".[dev,vision]"` en `kiosk-api`.

**Probar la webcam** con cualquier modelo YOLOv8 ONNX (por ejemplo, el preentrenado de `ml/data/models/`, que reconoce objetos genéricos como `bottle`):

```bash
cd kiosk-api
python -m kiosk.vision --model ../ml/data/models/yolov8n-416.onnx --camera 0
```

**Quiosco con cámara, por parecido (sin entrenar)**: una galería con las fotos de cada producto, DINOv2 y color. Guía completa (modelos a descargar, importar fotos del Drive, capturar fotos con la webcam): [`docs/ml/reconocimiento.md`](docs/ml/reconocimiento.md).

```bash
python -m kiosk.recognizer galeria          # desde ml/data/raw/<SKU>/
python -m kiosk.recognizer camara --camera 0 # prueba en vivo
KIOSK_MODE=camera KIOSK_GALLERY=../ml/data/models/galeria.npz python -m kiosk
```

**Quiosco con cámara, YOLOv8** (cuando exista el modelo entrenado con los productos del catálogo):

```bash
export KIOSK_MODE=camera
export KIOSK_MODEL=../ml/data/models/autocaja-416.onnx   # modelo entrenado (M1)
export KIOSK_CAMERA=0      # índice de la webcam
export KIOSK_IMGSZ=416     # tamaño con el que se exportó
python -m kiosk
```

En modo cámara no existen las rutas `/sim` ni el panel de simulación. Arranca con la bandeja vacía: los primeros cuadros son el fondo.

## Herramientas del dataset (`ml/`)

```bash
cd ml
python -m venv .venv && source .venv/Scripts/activate
pip install -e ".[dev,bench]"

python -m mltools.dataset_check                 # revisa data/raw/ contra el catálogo
python -m mltools.frames VIDEO.mp4 --out data/raw/SKU   # fotos desde un video
python -m mltools.labelstudio                   # configuración para Label Studio
python -m mltools.split                         # exportación de Label Studio → dataset 70/20/10
python -m mltools.train                         # entrena, evalúa (mAP50 ≥ 0,90) y exporta a ONNX
python -m mltools.bench --model modelo.onnx     # latencia vs RNF-01 (p95 ≤ 150 ms)
```

Guía de etiquetado: [`docs/ml/etiquetado.md`](docs/ml/etiquetado.md). Guía de entrenamiento: [`docs/ml/entrenamiento.md`](docs/ml/entrenamiento.md). Los datos (`ml/data/`) nunca van a git.
