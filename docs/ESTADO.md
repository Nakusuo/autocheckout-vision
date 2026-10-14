# Estado del proyecto — AutoCaja (auto-checkout por visión)

> Traspaso para la próxima sesión. Actualizado: **2026-10-13**.
>
> **Decisión (2026-10-12): reconocimiento por parecido, sin entrenar.** Con las 56 fotos del Drive (11 productos) no alcanza para YOLOv8; el modo cámara usa una galería de fotos + DINOv2 + color (91 % de aciertos, 98 % sin reversos). Ver [`ml/reconocimiento.md`](ml/reconocimiento.md). El **catálogo** pasó a esos 11 productos, con precios de bodega fijados para la demo (aprobados por el equipo; se cambian en `catalog/products.csv`).
>
> **Decisión del equipo (2026-10-10): no habrá balanza por ahora.** El quiosco corre con `KIOSK_SCALE=off` (por defecto) y cobra solo lo que reconoce la cámara. La lógica de peso sigue en el código y se enciende con `KIOSK_SCALE=sim` (o una balanza real en el futuro).
> Requisitos: [`SRS.md`](SRS.md) · Diseño aprobado: [`superpowers/specs/2026-10-03-autocheckout-design.md`](superpowers/specs/2026-10-03-autocheckout-design.md) · Hoja de ruta: [`superpowers/plans/2026-10-03-hoja-de-ruta.md`](superpowers/plans/2026-10-03-hoja-de-ruta.md) · Producto y diseño visual: [`../PRODUCT.md`](../PRODUCT.md), [`../DESIGN.md`](../DESIGN.md)

## 1. Dónde estamos

| | |
|---|---|
| `main` | **v0.1.0** etiquetada (PR #31): la versión de la demo. |
| `develop` | `main` + plan de calidad (auditoría y fases 1–3), hasta el PR #44. |
| `feature/demo-final` | PR #46 (incluye #45): zona de escaneo, mano, alertas de seguridad, ventas del día, aviso sonoro. Pendiente de merge; siguiente versión **v0.1.1**. |
| Pruebas | kiosk-api 247 (cobertura de ramas 96 %, mínima 90 % en CI) · kiosk-ui 91 · ml 39 · mock-gateway 13 · e2e Playwright 4 — todo en verde; CI con 6 jobs (incluye mypy y cobertura) |
| Mutación | Semanal (`.github/workflows/mutation.yml`): mutmut **90 %** (checkout, fusion, service) · Stryker **84 %** (pantallas W2/W3/QR, `format`) |
| Informe en Word | `docs/informe/Informe-AutoCaja.docx` (fuera de git; generado con capturas reales, diagramas y gráficos) |

**Ya no hay bloqueo de modelo:** el modo cámara reconoce los 11 productos con la galería de fotos (`KIOSK_GALLERY`). Falta probarlo con la webcam y la bandeja de la demo y sumar fotos tomadas ahí (`python -m kiosk.recognizer capturar SKU`).

## 2. Qué está hecho

**Hitos**
- **M0 Base**: monorepo, CI (ruff, bandit, oxlint, vitest, npm audit, gitleaks, Dependabot), catálogo, fusión de peso ±5 g, máquina de estados W1–W4.
- **M1a** herramientas del dataset (frames de video, verificador, Label Studio) y benchmark: **416 px** cumple RNF-01 (p95 126 ms con el YOLOv8n genérico).
- **M1b** `mltools.split` (70/20/10) y `mltools.train` (entrena, evalúa mAP50 ≥ 0.90, exporta ONNX). **Sin datos todavía.**
- **M2** FastAPI + WebSocket, SQLite (RNF-03), temporizadores 10 s / 120 s, UI 1080×1920 (RNF-06), panel de caja.
- **M3** `mock-gateway`: QR, «celular» simulado, JWT RS256 con `jti` anti-reenvío, TLS 1.3 (RNF-04/05).
- **M4** detector YOLOv8 ONNX + `KIOSK_MODE=camera`; **Playwright W1→W4** en CI (modo simulado).
- **M5 (código)**: registro de sesiones (`kiosk-api/sesiones.jsonl`) y `python -m kiosk.metrics` (tabla frente a ON-01/02/03 y RNF-02); boleta POS simulada (`kiosk-api/boletas.jsonl`); aviso Ley 29733 en W1/W2; plan de M5 y plantilla del informe. `kiosk.metrics` guarda la pantalla de cada cancelación e imprime «Cancelaciones por pantalla».
- **Cierre para la demo** (PR #45/#46): zona de escaneo (`KIOSK_ZONE=x0,y0,x1,y1` en fracciones; `python -m kiosk.recognizer zona …` guarda `zona.jpg`; `camara --zona`), filtro de mano (`KIOSK_HANDS`, encendido por defecto; `off` lo apaga: quita la piel de las manchas que tocan el borde de la zona), alertas de seguridad y ventas de hoy en `/caja`, pitido de 880 Hz con «Sonido: sí/no». Errores al arrancar la cámara (no abre, `KIOSK_CAMERA`/`KIOSK_ZONE` inválidos) terminan con un mensaje claro. El log va a consola y a `kiosk-api/kiosk.log` con hora (rota a 1 MB, guarda 3 anteriores).

**Interfaz**: identidad **AutoCaja** «señalética vial» en rojo/amarillo/blanco, sin nombre ni logo OXXO (ver `DESIGN.md`). Overpass empaquetada (funciona sin internet).

**Flujo actual del cliente** (PR #27):
1. W1 **INICIAR** → W2 «En vivo».
2. Pasa los productos **uno por uno** frente a la cámara; cada uno **se suma** («+ Agregado»). Botón «−» por línea para quitar una unidad.
   Con balanza (`KIOSK_SCALE=sim`), además la balanza confirma el peso de cada producto.
3. **CONFIRMAR** → W3 lista final → **PAGAR** → QR (Yape/Plin simulado) → W4 ticket → W1 a los 10 s.
4. **CANCELAR COMPRA** en W2, W3 y QR; **CORREGIR** en W3; **SOLICITAR AYUDA** siempre.

**Reglas clave del backend** (`kiosk-api/src/kiosk/service.py`):
- En modo cámara, `read_sensors()` (cámara + reconocimiento) corre en **otro hilo** (`create_app(threaded_sensing=True)`); el estado solo cambia en el bucle principal (`tick(reading)`). La cámara también lee en W1 para aprender la bandeja vacía; `/api/recalibrate` (botón en `/caja`) la reaprende.
- Un producto se suma cuando **entra** a la vista de la cámara (estable 3 cuadros); no se cuenta dos veces mientras sigue a la vista.
- **Balanza opcional** (`KIOSK_SCALE`, ver `__main__.scale_enabled`): con `off` (por defecto) `KioskService` recibe `scale=None`, no lee peso y PAGAR depende solo de lo escaneado; el snapshot trae `weight_enabled: false` y la UI oculta todo lo de peso.
- Con balanza: «Revise su bandeja» solo si el peso no coincide **más de 2 s** (`WEIGHT_GRACE_S`); PAGAR exige peso correcto.
- En modo cámara, CONFIRMAR cierra físicamente la webcam y congela la lista en W3/QR/W4; CORREGIR, cancelar o volver a W1 la abren. En modo simulado, un producto nuevo o desconocido en W3 sigue reabriendo W2.
- **Desconocidos**: solo se acumulan SKU del catálogo. En modo cámara no bloquean CONFIRMAR/PAGAR, pero se conserva su alerta de seguridad para `/caja`. En modo simulado bloquean mientras están a la vista. Si tapan un producto ya visto, al destaparlo puede contarse otra vez; revisa duplicados con «−». El tope de 50 alertas nunca descarta una de compra pagada o en curso.
- **Alertas de seguridad** (`GET /api/alerts`, `DELETE /api/alerts/{id}`): una por compra («Producto no reconocido frente a la cámara»), `times` cuenta las veces y `outcome` es en curso / pagada / cancelada / quiosco fuera de servicio. Si la caja la marca revisada y se repite en la misma compra, se crea otra. Ayudas y alertas pendientes: máximo 50.
- **Compromiso explícito**: sin balanza, un producto no reconocido puede salir sin pagar; la alerta (con resultado «pagada») es la mitigación.
- `GET /api/sales`: cantidad y total de hoy y las últimas 20 boletas.

**Plan de calidad** (tras la auditoría del equipo, 2026-10-12):
- Auditoría: validación de entradas (SKU, listas ≤ 20), `/docs` desactivado, mypy en CI, cobertura ≥ 90 %.
- Fase 1: e2e sin balanza, pruebas del modo cámara de punta a punta (`test_integration.py`) y de concurrencia.
- Fase 2: pruebas de mutación (mutmut + Stryker) y pruebas de valores exactos (`test_exact.py`, `screens.test.tsx`, `pago.test.tsx`).
- Fase 3: `boletas.jsonl`/`sesiones.jsonl` rotan a `*.1.jsonl` al pasar 5 MB (`kiosk/jsonl.py`; la numeración de boletas no se reinicia); la UI descarta estados del WebSocket mal formados (`isSnapshot`); TypeScript estricto; bandit sobre todo el paquete.
- **TypeScript se queda en 6**: Stryker 10 no funciona con TypeScript 7 (Dependabot ignora esa versión mayor).

**Paneles**: `/sim` (presentación: pasar por la cámara / sin escanear / sacar, escenarios paso a paso, balanza, acciones del quiosco, vista en vivo) y `/caja` (ayuda, alertas de seguridad, ventas de hoy, estado del quiosco, compra en curso, «Recalibrar cámara»). `/sim` es solo para el modo simulado; en modo cámara muestra un aviso.

## 3. Qué falta

**Del equipo (no es código)**
1. **Fotos con la webcam de la demo**: 10–20 por producto con `python -m kiosk.recognizer capturar SKU`, luego `galeria` y ajustar `KIOSK_THRESHOLD` (ver `docs/ml/reconocimiento.md`). El camino YOLOv8 (etiquetar ~100 fotos por producto) queda para después.
2. **Benchmark en la laptop de la demo** (`python -m kiosk.recognizer medir`) y anotar el resultado en `docs/ml/benchmark.md`.
3. **M5**: medir a 5 personas ajenas al equipo según `docs/superpowers/plans/2026-10-10-m5-demo.md` y llenar `docs/demo/informe-resultados.md` con `python -m kiosk.metrics`.
4. **ON-02 (peso)** queda **«No medido (sin balanza)»** en el informe mientras no haya balanza; `kiosk.metrics` ya lo marca así.
5. **Legal**: checklist del plan de M5 (aviso de cámara, permiso del cliente para usar sus colores, AGPL-3.0).

**De código** (todo lo planificado está hecho; queda lo que salga de las pruebas del equipo)
1. **Medir RNF-01 en la laptop de la demo** con `python -m kiosk.recognizer medir` (en desarrollo: ~110–150 ms por cuadro a 140 px). Si no cumple: modelo cuantizado (`dinov2-small-q.onnx`, mismo acierto) o 112 px.
2. **Probar el modo cámara en vivo** (`KIOSK_MODE=camera KIOSK_GALLERY=../ml/data/models/galeria.npz`) con la webcam de la demo; si había algo en la bandeja al arrancar, «Recalibrar cámara» en `/caja`.
3. Correcciones que salgan de esas pruebas → `v0.1.1`.

## 4. Riesgos y qué se puede mejorar

**Riesgos**
- **Sin balanza no hay antifraude por peso**: un producto que no pasa por la cámara no se detecta. Es aceptable para la demo; para un piloto real hace falta una balanza (HX711 + `SerialScale`, aún no implementada). Si se usa `KIOSK_SCALE=sim` en modo cámara, la balanza simulada sigue a la lista y tampoco valida nada (el log lo avisa).
- **Calibrar con datos reales**: `KIOSK_ZONE`, `StabilityFilter` (3 cuadros) y `KIOSK_THRESHOLD` se ajustaron sin la webcam y la bandeja de la demo.
- **Campo `camera` del snapshot**: en modo cámara significa «el detector puede recalibrar», no «hay cámara conectada».
- **Dependencias Python sin lockfile**: las versiones pueden cambiar entre instalaciones.
- **Vitest en Windows**: algunas primeras corridas terminan en «no tests» por arranque lento del worker (`pool: "threads"` ya puesto). Al repetir pasan; en CI (Linux) nunca falló. Si vuelve, probar `poolOptions` / más tiempo de arranque.

**Mejoras posibles**
- Mutación: quedan 51 mutantes vivos en el backend y 30 en la UI (la mayoría en Pago y Escaneo); ver el reporte del workflow.
- Reconocimiento: más fotos del frente de los productos parecidos (galletas en empaque rojo/blanco).
- E2E del modo cámara con imágenes grabadas.
- `SerialScale` (pyserial) para una balanza real.
- Hechas: e2e sin balanza; zona de escaneo y filtro de mano; etiqueta «+ Agregado» de la primera fila; ventas del día y aviso sonoro en `/caja`; pantalla de cada cancelación en las métricas; desconocido que dejaba la compra bloqueada (reportado por el equipo en la prueba con webcam del 2026-10-13).
- Diseño: el agente de revisión final de la skill de diseño no corrió (la pasada se hizo en el mismo hilo); hay una versión nueva de la skill Impeccable (v4.5.2) sin instalar.

## 5. Cómo correrlo (modo simulado)

```bash
# Una vez: claves de desarrollo (quedan en keys/, fuera de git)
cd mock-gateway && python -m gateway.devkeys

# Tres terminales, con la misma clave:  export GATEWAY_API_KEY=una-clave
cd mock-gateway && python -m gateway                 # HTTPS :8443
cd kiosk-api    && KIOSK_MODE=sim python -m kiosk    # :8000  (sin balanza; KIOSK_SCALE=sim para activarla)
cd kiosk-ui     && npm run dev                       # :5173
```

Quiosco `http://localhost:5173/` · Simulador `/sim` · Caja `/caja`. Pruebas e2e: `cd kiosk-ui && npm run e2e` (levanta todo solo; el quiosco debe estar en W1 si reutiliza servicios abiertos).
En Windows cada servicio usa su `.venv` (`./.venv/Scripts/python`). Ver también el README.
