# Diseño: Auto-Checkout por visión (MVP)

Fecha: 2026-10-03 · Estado: aprobado · Requisitos de origen: [`docs/SRS.md`](../../SRS.md)

## Contexto y restricciones del equipo

| Tema | Decisión | Motivo |
|---|---|---|
| Hardware | Solo laptops y webcam USB. La balanza y la pantalla táctil se **simulan**. | Es lo que hay disponible hoy. |
| Pagos | **Pasarela simulada** que reproduce el contrato de una pasarela real (QR + webhook JWT). | Yape/Plin no ofrecen una API pública de QR dinámico sin un convenio de comercio. |
| Licencia | **AGPL-3.0** para todo el repositorio. | YOLOv8 (Ultralytics) es AGPL-3.0. Si se usa comercialmente, se negocia la licencia de Ultralytics. |
| Catálogo | **5 a 10 productos** reales, fotografiados por el equipo. | No existe un dataset público de productos OXXO Perú. |
| Equipo | 4 a 6 personas en 5 frentes. | Ver «Organización». |

## Arquitectura (monorepo)

| Carpeta | Responsabilidad | Frente |
|---|---|---|
| `ml/` | Captura de fotos con la webcam, etiquetado (Label Studio local), entrenamiento de YOLOv8n, exportación a ONNX, evaluación (mAP) y benchmark de latencia | IA |
| `catalog/` | Semilla del catálogo: SKU, nombre, precio en céntimos, **peso real con envase** en gramos | Datos |
| `kiosk-api/` | FastAPI. Módulos `vision`, `scale`, `catalog` (SQLite), `checkout` (máquina de estados y fusión sensorial), `payments`, `help` | Backend + balanza |
| `kiosk-ui/` | React + Vite + TypeScript, 1080×1920 vertical, pantallas W1, W2, W3, QR, W4 y fuera de servicio | UI/UX |
| `mock-gateway/` | FastAPI: crea el cobro y el QR, página «simular pago desde el celular» y webhook firmado con RS256 | Pagos + seguridad |
| `tools/scale-sim/` | Balanza simulada: modo normal (peso teórico ± ruido de 2 g) y modo trampa (añade o quita peso) | Backend + balanza |

### Interfaces cambiables (puertos)

- `Detector.detect(frame) -> list[Detection(sku, confianza, bbox)]`. Implementaciones: `YoloOnnxDetector` y `ReplayDetector` (imágenes grabadas, para pruebas).
- `ScaleReader.stream() -> grams`. Implementaciones: `SerialScale` (pyserial, para el futuro HX711) y `SimulatedScale`.
- `PaymentGateway.create_charge(monto) -> Charge(id, qr_payload)` y `verify_webhook(token) -> PaymentEvent`. Implementaciones: `MockGateway` y, más adelante, la pasarela real.

## Flujo de datos

1. **W1**: el cliente pulsa INICIAR → la API pasa al estado `SCANNING`.
2. La webcam envía unos 5 fps al `Detector`. La lista se considera **estable** cuando el mismo conjunto de SKU aparece en 3 cuadros seguidos.
3. **W2**: se muestran el nombre, la cantidad y el precio unitario. Si hay 0 productos válidos, no se puede avanzar (3.4.1.4). Si hay más de 3, aparece el aviso «use la caja».
4. Fusión: `teórico = Σ peso_catálogo`. La balanza envía su lectura de forma continua y PAGAR se habilita solo si `|real − teórico| ≤ 5 g`. Si no, se muestra «Revise su bandeja».
5. **W3**: el cliente confirma o pulsa CORREGIR (vuelve a W2).
6. PAGAR → `create_charge` → se muestra el QR. Se espera el webhook (y se consulta el estado como respaldo) con un límite de **120 s**.
7. Webhook con JWT RS256 válido → venta `PAID` → boleta del POS **simulada** (queda en un log) → **W4** → a los 10 s vuelve a W1.

La UI recibe el estado, las detecciones y el peso por **WebSocket** desde `kiosk-api`.

## Errores

| Situación | Comportamiento |
|---|---|
| Cámara o balanza desconectada | Pantalla «Fuera de servicio» y alerta automática a la caja |
| Más de 3 productos | Aviso «Para más de 3 productos use la caja» |
| El pago no llega en 120 s | Se cancela el cobro y se vuelve a W3 |
| JWT inválido o expirado | Se rechaza (401), queda en el log y la venta no se cierra |
| SOLICITAR AYUDA | Visible en todas las pantallas. Emite un evento al panel de caja (vista web sencilla) |

## Seguridad

- Los secretos y claves privadas **nunca** van al repositorio: `.env` y `keys/` están en `.gitignore`. Hay un script para generar el par de claves RS256.
- El JWT incluye `iss`, `aud`, `exp` (máximo 5 min) y `jti`, que se guarda para impedir que se reutilice el mismo webhook.
- TLS 1.3 en los servicios expuestos. En desarrollo se usan certificados de `mkcert`.
- CI: gitleaks, bandit, ruff, eslint, `npm audit` y Dependabot.

## Aspectos legales

- `LICENSE` AGPL-3.0. Si el sistema se ofrece por red, hay que dar acceso al código fuente.
- **Ley 29733** (protección de datos personales, Perú): la cámara apunta solo a la bandeja y no se guardan imágenes de personas. Las fotos para reentrenar solo se guardan con un aviso visible y consentimiento.
- **Marca OXXO**: la interfaz usa una marca genérica. Su logo y su nombre no se usan sin autorización.
- La boleta electrónica de SUNAT y la integración con el POS real quedan fuera del MVP; esa parte se simula.

## Pruebas

- `kiosk-api`: pytest con TDD para la fusión, la máquina de estados y la verificación del JWT.
- `ml`: mAP50 ≥ 0.90 sobre el conjunto de prueba y **benchmark del RNF-01 (≤ 150 ms)** en la laptop del equipo. **Riesgo**: en CPU, YOLOv8n con ONNX puede quedar cerca del límite; si no se cumple, se baja la imagen a 416 px o se usa OpenVINO.
- `kiosk-ui`: Playwright de W1 a W4 usando `ReplayDetector`, `SimulatedScale` y `MockGateway`.
- RNF-02: se cronometra a 5 personas fuera del equipo en la demo (≤ 45 s).

## Organización

- GitHub privado `autocheckout-vision`. Gitflow: `main` (versiones), `develop` (integración) y `feature/*`.
- Etiquetas por frente: `frente:ia`, `frente:datos`, `frente:backend`, `frente:ui-ux`, `frente:pagos-seguridad`. Etiquetas de triage: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`.
- Hitos:
  - **M0** Base: repo, CI y simuladores.
  - **M1** Datos y modelo.
  - **M2** Flujo W1–W4 con simuladores.
  - **M3** Pagos y seguridad.
  - **M4** Integración con la webcam.
  - **M5** Demo y medición.

## Fuera de alcance (MVP)

Balanza física, pantalla táctil real, pasarela real, POS/SUNAT real, más de 3 productos y productos a granel.
