# AutoCaja (autocheckout-vision) — Documento informativo del proyecto

> Generado el 2026-11-16 con graphify (análisis estructural del código) más la lectura de `README.md`, `PRODUCT.md` y `docs/ESTADO.md`. Las cifras de pruebas y del estado del proyecto vienen de `docs/ESTADO.md` (actualizado el 2026-10-13), no se volvieron a medir.

## 1. Qué es

**AutoCaja** es un quiosco de autocobro para una tienda de conveniencia (caso de estudio: OXXO, Av. Túpac Amaru, Comas, Lima). El cliente deja de 1 a 3 productos en una bandeja y no escanea nada. Una cámara cenital reconoce los productos, una balanza opcional confirma el peso y el cliente paga con un QR (Yape/Plin simulado).

Es el MVP de un equipo universitario. El hardware (balanza, pantalla táctil, pasarela de pago) está simulado y la demo corre en una laptop. Licencia: AGPL-3.0.

**Metas del SRS**

| ID | Meta |
|---|---|
| ON-01 / RNF-02 | Cobro completo en ≤ 45 s |
| ON-02 | Pago solo con peso validado (±5 g) |
| ON-03 | ≥ 80 % de compras sin pedir ayuda |
| RNF-01 | Inferencia de la IA ≤ 150 ms (p95) |
| RNF-03 | Catálogo y pesos en base local (SQLite) |
| RNF-04 / 05 | Pagos por TLS 1.3 con tokens JWT firmados con clave asimétrica (RS256) |
| RNF-06 | Interfaz vertical para pantalla táctil (1080×1920) |

## 2. Arquitectura

Cuatro componentes en un monorepo:

| Carpeta | Rol | Tecnología |
|---|---|---|
| `kiosk-api/` | Cerebro del quiosco: máquina de estados, reconocimiento, balanza, pagos, API y WebSocket | Python 3.12, FastAPI, SQLite, ONNX Runtime |
| `kiosk-ui/` | Interfaz del cliente (`/`), simulador para la demo (`/sim`) y panel de caja (`/caja`) | React + Vite, TypeScript estricto |
| `mock-gateway/` | Pasarela de pago simulada: QR, «celular» que paga, JWT RS256 con `jti` anti-reenvío | Python, HTTPS TLS 1.3 |
| `ml/` | Herramientas del dataset: frames desde video, verificación, Label Studio, split 70/20/10, entrenamiento, benchmark | Python, YOLOv8 / Ultralytics |

Datos y documentación: `catalog/products.csv` (catálogo), `docs/` (SRS, diseño, planes, guías de ML, informe de la demo).

```
Cámara ─▶ Detector (YOLOv8 ONNX o galería DINOv2+color) ─┐
Balanza (opcional) ──────────────────────────────────────┼▶ Fusión ▶ KioskService ▶ API + WebSocket ▶ UI
                                                          │   (peso ±5 g)  (estados W1–W4)
Pasarela mock ◀── HTTPS TLS 1.3 + JWT RS256 ──────────────┘
```

### Módulos principales de `kiosk-api/src/kiosk/`

| Módulo | Qué hace |
|---|---|
| `service.py` (`KioskService`) | Núcleo: el nodo más conectado del grafo (68 conexiones). Orquesta sensores, estados, temporizadores (10 s / 120 s), alertas y ayuda |
| `checkout.py` | Máquina de estados W1–W4 y errores de transición (`TransitionError`) |
| `fusion.py` | Comparación de peso esperado y medido (±5 g) |
| `stability.py` | Filtro de estabilidad: un producto cuenta cuando está estable 3 cuadros |
| `recognizer.py` | Reconocimiento por parecido: galería de fotos, DINOv2 y color. CLI: `galeria`, `camara`, `capturar`, `zona`, `medir`, `evaluar` |
| `vision.py` | Detector YOLOv8 ONNX (letterbox, decodificación), prueba de webcam |
| `tray.py` | Bandeja y detectores, simulados o reales |
| `scale.py` | Balanza simulada (`SimulatedScale`); la balanza real (`SerialScale`) no está implementada |
| `catalog.py`, `store.py` | Catálogo y persistencia SQLite |
| `payments.py`, `pos.py` | Cobro contra la pasarela (verifica firma RS256) y boleta POS simulada (serie `B001`) |
| `metrics.py`, `jsonl.py` | Registro de sesiones y boletas en JSONL con rotación a 5 MB; resumen frente al SRS |
| `app.py` (`create_app()`) | API FastAPI: 44 conexiones en el grafo |
| `__main__.py` | Arranque y lectura de variables de entorno |

## 3. Flujo del cliente

1. **W1 Inicio** → INICIAR.
2. **W2 Escaneo**: el cliente pasa los productos uno por uno. Cada uno se suma («+ Agregado») y se puede quitar con «−».
3. **W3 Confirmar**: lista final. CONFIRMAR → PAGAR, o CORREGIR para volver a W2.
4. **QR de pago**: Yape/Plin simulado, con espera de hasta 120 s.
5. **W4 Ticket**: vuelve a W1 a los 10 s.
6. **Siempre disponibles**: SOLICITAR AYUDA, y CANCELAR COMPRA en W2, W3 y QR. También existe la pantalla Fuera de servicio.

**Reglas clave**
- En modo cámara, el reconocimiento corre en otro hilo. El estado solo cambia en el bucle principal.
- Los productos desconocidos no bloquean CONFIRMAR ni PAGAR en modo cámara, pero generan una alerta de seguridad en `/caja`. En modo simulado sí bloquean.
- CONFIRMAR cierra físicamente la webcam y congela la lista hasta CORREGIR, cancelar o volver al inicio.
- La zona de escaneo (`KIOSK_ZONE`) y el filtro de mano (`KIOSK_HANDS`) acotan lo que cuenta.

## 4. Reconocimiento de productos

Hay dos caminos:

| Camino | Estado |
|---|---|
| **Por parecido (galería)**: fotos de cada producto, DINOv2 y color | **En uso.** Decisión del 2026-10-12. Con 56 fotos del Drive de 11 productos se obtiene 91 % de aciertos (98 % sin reversos) |
| **YOLOv8 entrenado** (`ml/`) | Herramientas listas (`split`, `train` con meta mAP50 ≥ 0,90, exportación ONNX), pero **sin dataset suficiente** todavía |

Latencia (RNF-01): el benchmark con el YOLOv8n genérico a 416 px dio p95 de 126 ms. El reconocedor por galería tarda ~110–150 ms por cuadro a 140 px en desarrollo. Falta medirlo en la laptop de la demo.

## 5. Catálogo (11 productos)

| SKU | Producto | Precio | Peso |
|---|---|---|---|
| CANCUN-33 | Bizcocho Cancún 33 g | S/ 1.50 | 36 g |
| CASINO-43 | Galletas Casino 43 g | S/ 1.50 | 46 g |
| CHOCMAN-39 | Chocman 39 g | S/ 1.50 | 42 g |
| CLUBSOCIAL-24 | Galletas Club Social 24 g | S/ 1.30 | 26 g |
| GLACITAS-30G | Glacitas 30 g | S/ 1.50 | 33 g |
| GUARANA-450 | Guaraná 450 ml | S/ 3.00 | 470 g |
| KRPINA-3.03L | KR Piña 3.03 L | S/ 6.00 | 3100 g |
| MOROCHAS-30 | Galletas Morochas 30 g | S/ 1.50 | 33 g |
| RITZ-20 | Galletas Ritz 20 g | S/ 1.30 | 22 g |
| VIZZIO-19 | Vizzio 19 g | S/ 3.00 | 21 g |
| YOFRESH-190 | Yofresh 190 ml | S/ 2.00 | 200 g |

Los precios son de bodega y están fijados para la demo. Se cambian en `catalog/products.csv`.

## 6. Interfaz y paneles

| Ruta | Para qué |
|---|---|
| `/` | Quiosco del cliente, formato vertical 9:16. Identidad **AutoCaja** «señalética vial» en rojo/amarillo/blanco, sin nombre ni logo de OXXO (ver `DESIGN.md`). Fuente Overpass empaquetada, funciona sin internet |
| `/sim` | Simulador para la presentación: pasar productos por la cámara, escenarios, balanza, acciones del quiosco, celular que paga. Solo en modo simulado |
| `/caja` | Panel de caja: ayudas pedidas, alertas de seguridad (`/api/alerts`), ventas de hoy (`/api/sales`), reactivar el quiosco, recalibrar la cámara, pitido de 880 Hz con cada aviso |

Principios de producto: un paso, una decisión · estado siempre visible · nadie se queda atascado · legible de pie. Accesibilidad: blancos táctiles grandes, contraste WCAG AA y estados que no dependen solo del color.

## 7. Calidad y CI

Cifras al 2026-10-13, tomadas de `docs/ESTADO.md`:

| Área | Estado |
|---|---|
| Pruebas | kiosk-api 247 (cobertura de ramas 96 %, mínimo 90 % en CI) · kiosk-ui 91 · ml 39 · mock-gateway 13 · e2e Playwright 4 |
| CI (6 jobs) | ruff, mypy, bandit, oxlint, vitest, npm audit, gitleaks, Dependabot |
| Mutación (semanal) | mutmut 90 % (checkout, fusion, service) · Stryker 84 % (pantallas W2/W3/QR, `format`) |
| Seguridad | Validación de entradas, `/docs` desactivado, TLS 1.3, JWT RS256 con `jti` anti-reenvío, CORS solo a `localhost:5173` |
| Privacidad | Aviso de la Ley 29733 en W1/W2 |

## 8. Cómo correrlo (modo simulado)

```bash
# Una vez: claves de desarrollo
cd mock-gateway && python -m gateway.devkeys

# Tres terminales, con la misma clave:  export GATEWAY_API_KEY=una-clave-larga
cd mock-gateway && python -m gateway          # HTTPS :8443
cd kiosk-api    && python -m kiosk            # :8000
cd kiosk-ui     && npm install && npm run dev # :5173
```

Modo cámara: `KIOSK_MODE=camera KIOSK_GALLERY=../ml/data/models/galeria.npz python -m kiosk`. Variables útiles: `KIOSK_SCALE` (`off` por defecto o `sim`), `KIOSK_ZONE`, `KIOSK_HANDS`, `KIOSK_THRESHOLD`, `KIOSK_CAMERA`. Pruebas e2e: `cd kiosk-ui && npm run e2e`.

## 9. Estado y siguientes pasos

**Hecho**
- Hitos M0 a M5 en el código: base, herramientas ML, flujo, pagos, cámara y demo.
- `main` en la versión v0.1.0. Después hubo correcciones del modo cámara (PR #53 y #54, p. ej. agrupar fragmentos superpuestos antes de reconocer).

**Falta (sobre todo del equipo, no de código)**
1. Tomar 10–20 fotos por producto con la webcam de la demo (`python -m kiosk.recognizer capturar SKU`), reconstruir la galería y ajustar `KIOSK_THRESHOLD`.
2. Medir RNF-01 en la laptop de la demo (`python -m kiosk.recognizer medir`) y anotarlo en `docs/ml/benchmark.md`.
3. Medir con 5 personas ajenas al equipo y llenar `docs/demo/informe-resultados.md` con `python -m kiosk.metrics`.
4. Revisión legal: aviso de cámara, permiso del cliente para usar sus colores, AGPL-3.0.

**Riesgos conocidos**
- **Sin balanza no hay antifraude por peso.** Un producto que no pasa por la cámara no se detecta. La alerta de seguridad es solo una mitigación. ON-02 queda «No medido (sin balanza)». Un piloto real necesita balanza física (HX711 + `SerialScale`).
- Zona, filtro de estabilidad y umbral se ajustaron sin la webcam ni la bandeja de la demo.
- Las dependencias Python no tienen lockfile.
- TypeScript se queda en la versión 6 porque Stryker 10 no funciona con TypeScript 7.

**Mejoras posibles:** más fotos de productos parecidos (galletas en empaque rojo/blanco), e2e del modo cámara con imágenes grabadas, balanza serial real, y pasarela y POS/SUNAT reales para un piloto.

## 10. Radiografía del código (graphify)

Grafo construido solo sobre el código (análisis estructural, sin LLM): **105 archivos de código**, 1183 nodos, 2992 aristas y 66 comunidades. Por proyecto: kiosk-api 667 nodos, kiosk-ui 238, ml 104, mock-gateway 48. Un 88 % de las aristas es explícito en el código (EXTRACTED) y un 12 % es inferido (INFERRED, confianza media 0,91). No hay ciclos de importación.

**Abstracciones centrales** (nodos más conectados): `KioskService` (68), `create_app()` (44), `SimulatedScale` (35), `TransitionError` (32), `JwtVerifier` (32), `SimulatedTray` (30). `tray()`, `make()`, `ticks()` y `FakeGateway` también aparecen arriba, pero son ayudas de pruebas.

**Observaciones**
- El peso del proyecto está en el backend de visión y estados. `recognizer.py` y `service.py` son los archivos de código con más símbolos.
- Las pruebas son una parte grande del grafo (`test_service.py` es el archivo con más nodos), coherente con las 247 pruebas del backend.
- `build_detector()` en `__main__.py` es el punto de ensamblaje: une catálogo, detectores, balanza y bandeja.
- Siete archivos no dieron símbolos (configuración y archivos de arranque como `main.tsx`, `vite.config.ts`).
- Los documentos (`docs/*.md`) no pasaron por extracción semántica. Esta sección describe solo el código; el resto sale de la lectura de los documentos.

Los artefactos del grafo no se guardan en el repositorio. Se regeneran con `/graphify .`.
