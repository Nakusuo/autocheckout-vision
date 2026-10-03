# Hoja de ruta: Auto-Checkout por visión (MVP)

**Spec:** [`docs/superpowers/specs/2026-10-03-autocheckout-design.md`](../specs/2026-10-03-autocheckout-design.md)

Cada hito tiene su propio plan detallado (`docs/superpowers/plans/`), que se escribe al empezar ese hito. Así cada plan parte del código que realmente existe en ese momento. En GitHub, cada hito es un *milestone* y cada tarea es un *issue*.

## Frentes

| Frente | Etiqueta | Responsable |
|---|---|---|
| IA (modelo YOLOv8) | `frente:ia` | _(asignar)_ |
| Datos y catálogo | `frente:datos` | _(asignar)_ |
| Backend y balanza | `frente:backend` | _(asignar)_ |
| UI/UX del quiosco | `frente:ui-ux` | _(asignar)_ |
| Pagos y seguridad | `frente:pagos-seguridad` | _(asignar)_ |

## Hitos

| Hito | Entregable verificable | Frentes | Plan |
|---|---|---|---|
| **M0 Base** | Monorepo con CI en verde. Núcleo de `kiosk-api` probado: catálogo, fusión de peso (±5 g), estabilidad de la detección, máquina de estados W1–W4 y balanza simulada | backend, pagos-seguridad | [`2026-10-03-m0-base.md`](2026-10-03-m0-base.md) |
| **M1 Datos y modelo** | De 5 a 10 productos pesados con envase; unas 100 fotos por producto etiquetadas en Label Studio; YOLOv8n entrenado con mAP50 ≥ 0.90; exportado a ONNX; benchmark ≤ 150 ms (RNF-01) | ia, datos | por escribir |
| **M2 Flujo con simuladores** | `kiosk-api` con FastAPI y WebSocket, catálogo en SQLite (RNF-03), temporizadores de 10 s y 120 s; `kiosk-ui` con las pantallas W1, W2, W3, QR, W4 y fuera de servicio en 1080×1920 (RNF-06); panel de caja para SOLICITAR AYUDA | backend, ui-ux | por escribir |
| **M3 Pagos y seguridad** | `mock-gateway`: crea el cobro, genera el QR, tiene la página «simular pago» y envía el webhook con JWT RS256 (`iss`, `aud`, `exp`, `jti` contra reenvíos); TLS 1.3 con mkcert (RNF-04/05) | pagos-seguridad | por escribir |
| **M4 Integración con webcam** | `YoloOnnxDetector` conectado a la webcam real; Playwright de W1 a W4 con `ReplayDetector` en CI | ia, backend, ui-ux | por escribir |
| **M5 Demo y medición** | Cronometrar a 5 personas ajenas al equipo (≤ 45 s, RNF-02); informe de resultados frente a ON-01/02/03; revisión legal (avisos de la Ley 29733, marca genérica) | todos | por escribir |

## Dependencias

```
M0 ──► M2 ──► M3 ──► M4 ──► M5
M1 ─────────────────► M4
```

M1 (datos y modelo) **se trabaja en paralelo** desde el primer día, porque fotografiar y etiquetar es lo más lento.

## Tareas manuales del equipo (no son código)

- Comprar los productos del catálogo y una balanza de cocina; anotar el peso **con envase**.
- Instalar Label Studio local (`pip install label-studio`) para etiquetar.
- Avisar al cliente sobre el uso de la marca OXXO y la política de cámara (Ley 29733).
