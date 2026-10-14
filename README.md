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
| http://localhost:5173/caja | Panel de caja: solicitudes de ayuda, alertas de seguridad, ventas de hoy, reactivar el quiosco y recalibrar la cámara |

**Panel de caja (`/caja`):**
- **Alertas de seguridad** (`GET /api/alerts`, `DELETE /api/alerts/{id}` al marcarla revisada): una por compra cuando pasa algo no reconocido frente a la cámara («Producto no reconocido frente a la cámara»). Cuenta las veces (`times`) y dice cómo terminó la compra: en curso, pagada, cancelada o quiosco fuera de servicio. Si la caja la marca revisada y vuelve a pasar en la misma compra, se crea otra.
- **Ventas de hoy** (`GET /api/sales`): cantidad y total del día y las últimas 20 boletas.
- Pitido (880 Hz) con cada ayuda o alerta nueva; el botón «Sonido: sí/no» se recuerda en el navegador.
- Se guardan hasta 50 ayudas y 50 alertas sin atender.

Para pagar: en la pantalla del QR, abre en `/sim` el enlace «Abrir el celular simulado» y pulsa «Pagar con Yape/Plin (simulado)». El quiosco consulta la pasarela por HTTPS (TLS 1.3), verifica la firma RS256 y muestra el ticket.

La API escucha en 127.0.0.1:8000 y solo acepta peticiones desde http://localhost:5173 (Vite usa ese puerto fijo; si está ocupado, libéralo).

**Balanza:** por defecto no se usa (`KIOSK_SCALE=off`): el quiosco cobra lo que reconoce la cámara. Con `KIOSK_SCALE=sim` se activa la balanza simulada y la validación de peso (±5 g, ON-02), con la trampa de peso en `/sim`.

Cada venta pagada emite una boleta simulada del POS (serie `B001`) que se guarda en `kiosk-api/boletas.jsonl` (fuera de git).

Cada compra queda registrada en `kiosk-api/sesiones.jsonl` (duración de INICIAR a W4, ayuda pedida, alertas de peso). `python -m kiosk.metrics` en `kiosk-api` resume esos datos frente a las metas del SRS (ON-01/02/03, RNF-02) e imprime las cancelaciones por pantalla; se usa en la demo, ver [`docs/superpowers/plans/2026-10-10-m5-demo.md`](docs/superpowers/plans/2026-10-10-m5-demo.md). Ambos archivos rotan al pasar 5 MB a `<nombre>.1.jsonl` (se guarda una sola copia anterior).

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

**Zona de escaneo y mano:**

```bash
python -m kiosk.recognizer zona 0.25,0.1,0.75,0.9   # guarda zona.jpg con el recuadro dibujado
python -m kiosk.recognizer camara --camera 0 --zona 0.25,0.1,0.75,0.9
export KIOSK_ZONE=0.25,0.1,0.75,0.9                  # x0,y0,x1,y1 en fracciones; fuera del recuadro no cuenta
export KIOSK_HANDS=off                               # opcional: por defecto se quita la piel que entra por el borde de la zona
```

**Lo que no se reconoce:** solo se suman productos del catálogo. En modo cámara, las detecciones desconocidas no bloquean CONFIRMAR ni PAGAR y no se agregan a la lista. Cada compra con un desconocido sigue generando una alerta de seguridad en `/caja`. En modo simulado, un desconocido a la vista sigue bloqueando el pago y reabre W2 desde W3. Si tapa un producto ya visto, al destaparlo se puede contar otra vez: revisa la lista y quita duplicados con «−».

**Confirmación con webcam:** CONFIRMAR se habilita desde el primer producto reconocido (máximo 3); cierra físicamente la webcam y congela la lista hasta CORREGIR, cancelar o volver al inicio después del ticket. Con balanza, PAGAR sigue exigiendo peso correcto.

**Riesgo aceptado:** sin balanza, un producto que no se reconoce puede salir sin pagar. La alerta de seguridad (que termina en «pagada») es la mitigación: la caja revisa esa compra.

En modo cámara no existen las rutas `/sim`; el panel `/sim` solo muestra un aviso. Arranca con la bandeja vacía: los primeros cuadros son el fondo. Si la cámara no abre o `KIOSK_CAMERA`/`KIOSK_ZONE` no son válidos, el quiosco termina con un mensaje claro.

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
