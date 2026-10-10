# Estado del proyecto — AutoCaja (auto-checkout por visión)

> Traspaso para la próxima sesión. Actualizado: **2026-10-10**.
> Requisitos: [`SRS.md`](SRS.md) · Diseño aprobado: [`superpowers/specs/2026-10-03-autocheckout-design.md`](superpowers/specs/2026-10-03-autocheckout-design.md) · Hoja de ruta: [`superpowers/plans/2026-10-03-hoja-de-ruta.md`](superpowers/plans/2026-10-03-hoja-de-ruta.md) · Producto y diseño visual: [`../PRODUCT.md`](../PRODUCT.md), [`../DESIGN.md`](../DESIGN.md)

## 1. Dónde estamos

| | |
|---|---|
| Rama de integración | `develop` (tiene M0–M5 en código: PRs #17–#26) |
| **PR abierto** | **#27** `feature/sim-caja` → `develop`, CI en verde, **falta fusionarlo** (escaneo uno por uno, cancelar, paneles /sim y /caja). Este archivo viaja en ese PR. |
| `main` | Solo el commit inicial. Falta una versión (`develop` → `main`, p. ej. `v0.1.0`) antes de la demo. |
| Pruebas (local, rama #27) | kiosk-api 117 · kiosk-ui 24 · ml 34 · mock-gateway 13 · e2e Playwright 2 — todo en verde; CI con 6 jobs en verde |

**Bloqueo principal: no hay modelo entrenado.** El quiosco funciona de punta a punta en **modo simulado**; el modo cámara existe pero necesita el modelo de los 5 productos del catálogo.

## 2. Qué está hecho

**Hitos**
- **M0 Base**: monorepo, CI (ruff, bandit, oxlint, vitest, npm audit, gitleaks, Dependabot), catálogo, fusión de peso ±5 g, máquina de estados W1–W4.
- **M1a** herramientas del dataset (frames de video, verificador, Label Studio) y benchmark: **416 px** cumple RNF-01 (p95 126 ms con el YOLOv8n genérico).
- **M1b** `mltools.split` (70/20/10) y `mltools.train` (entrena, evalúa mAP50 ≥ 0.90, exporta ONNX). **Sin datos todavía.**
- **M2** FastAPI + WebSocket, SQLite (RNF-03), temporizadores 10 s / 120 s, UI 1080×1920 (RNF-06), panel de caja.
- **M3** `mock-gateway`: QR, «celular» simulado, JWT RS256 con `jti` anti-reenvío, TLS 1.3 (RNF-04/05).
- **M4** detector YOLOv8 ONNX + `KIOSK_MODE=camera`; **Playwright W1→W4** en CI (modo simulado).
- **M5 (código)**: registro de sesiones (`kiosk-api/sesiones.jsonl`) y `python -m kiosk.metrics` (tabla frente a ON-01/02/03 y RNF-02); boleta POS simulada (`kiosk-api/boletas.jsonl`); aviso Ley 29733 en W1/W2; plan de M5 y plantilla del informe.

**Interfaz**: identidad **AutoCaja** «señalética vial» en rojo/amarillo/blanco, sin nombre ni logo OXXO (ver `DESIGN.md`). Overpass empaquetada (funciona sin internet).

**Flujo actual del cliente** (PR #27):
1. W1 **INICIAR** → W2 «En vivo».
2. Pasa los productos **uno por uno** frente a la cámara; cada uno **se suma** («+ Agregado»). Lo deja en la bandeja y la balanza confirma el peso. Botón «−» por línea para quitar una unidad.
3. **CONFIRMAR** → W3 lista final → **PAGAR** → QR (Yape/Plin simulado) → W4 ticket → W1 a los 10 s.
4. **CANCELAR COMPRA** en W2, W3 y QR; **CORREGIR** en W3; **SOLICITAR AYUDA** siempre.

**Reglas clave del backend** (`kiosk-api/src/kiosk/service.py`):
- Un producto se suma cuando **entra** a la vista de la cámara (estable 3 cuadros); no se cuenta dos veces mientras sigue a la vista.
- «Revise su bandeja» solo si el peso no coincide **más de 2 s** (`WEIGHT_GRACE_S`); PAGAR siempre exige peso correcto.
- En W3, un producto nuevo frente a la cámara **reabre W2** (antifraude, tras una revisión de seguridad).

**Paneles**: `/sim` (presentación: pasar por la cámara / sin escanear / sacar, escenarios paso a paso, balanza, acciones del quiosco, vista en vivo) y `/caja` (ayuda, estado del quiosco, compra en curso).

## 3. Qué falta

**Del equipo (no es código)**
1. **Dataset**: ~100 fotos por producto (5 productos), etiquetar en Label Studio, `python -m mltools.split` y `python -m mltools.train` hasta mAP50 ≥ 0.90. Guías: `docs/ml/etiquetado.md`, `docs/ml/entrenamiento.md`.
2. **Benchmark en la laptop de la demo** (`python -m mltools.bench`) y anotar en `docs/ml/benchmark.md`.
3. **M5**: medir a 5 personas ajenas al equipo según `docs/superpowers/plans/2026-10-10-m5-demo.md` y llenar `docs/demo/informe-resultados.md` con `python -m kiosk.metrics`.
4. **Legal**: checklist del plan de M5 (aviso de cámara, permiso del cliente para usar sus colores, AGPL-3.0).

**De código**
1. **Fusionar PR #27** a `develop`.
2. **Conectar el modelo entrenado** (`KIOSK_MODE=camera`, `KIOSK_MODEL=...onnx`) y probar el escaneo uno por uno con la webcam real (ver «Riesgos»).
3. **Versión para la demo**: PR `develop` → `main` y etiqueta `v0.1.0`.

## 4. Riesgos y qué se puede mejorar

**Riesgos**
- **Modo cámara sin balanza física**: la balanza simulada sigue a la lista, así que **el peso no valida nada** (el log lo avisa al arrancar). Para la demo con cámara, la validación de peso se muestra mejor en modo simulado o con una balanza real (HX711 + `SerialScale`, aún no implementada).
- **Escaneo uno por uno con la cámara real**: la cámara cenital ve la bandeja entera; para «uno por uno» conviene una **zona de escaneo** separada de la bandeja (o recortar la imagen a esa zona) y ajustar `StabilityFilter` (3 cuadros) y el umbral de confianza con datos reales.
- **Vitest en Windows**: algunas primeras corridas terminan en «no tests» por arranque lento del worker (`pool: "threads"` ya puesto). Al repetir pasan; en CI (Linux) nunca falló. Si vuelve, probar `poolOptions` / más tiempo de arranque.

**Mejoras posibles**
- E2E Playwright del flujo **uno por uno** con `/sim/scan` (hoy las e2e usan `/sim/tray`, que coloca todo junto), y de CANCELAR y del producto «sin escanear».
- E2E en **modo cámara** con imágenes grabadas (`ImageFolderSource`) cuando exista el modelo.
- `SerialScale` (pyserial) para una balanza real.
- La etiqueta «+ Agregado» de la **primera** fila roza el borde superior del tablero en W2 (detalle visual menor).
- `/caja`: historial de ventas del día (leer `boletas.jsonl`) y avisos sonoros de ayuda.
- Métricas: guardar también qué pantalla generó cada cancelación para el informe.
- Diseño: el agente de revisión final de la skill de diseño no corrió (la pasada se hizo en el mismo hilo); hay una versión nueva de la skill Impeccable (v4.5.2) sin instalar.

## 5. Cómo correrlo (modo simulado)

```bash
# Una vez: claves de desarrollo (quedan en keys/, fuera de git)
cd mock-gateway && python -m gateway.devkeys

# Tres terminales, con la misma clave:  export GATEWAY_API_KEY=una-clave
cd mock-gateway && python -m gateway                 # HTTPS :8443
cd kiosk-api    && KIOSK_MODE=sim python -m kiosk    # :8000
cd kiosk-ui     && npm run dev                       # :5173
```

Quiosco `http://localhost:5173/` · Simulador `/sim` · Caja `/caja`. Pruebas e2e: `cd kiosk-ui && npm run e2e` (levanta todo solo; el quiosco debe estar en W1 si reutiliza servicios abiertos).
En Windows cada servicio usa su `.venv` (`./.venv/Scripts/python`). Ver también el README.
