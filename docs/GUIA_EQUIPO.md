# Guía del equipo — cómo llegar a la máxima nota (APF 3)

Léela primero. Dice qué falta, quién puede tomarlo y cómo usar el grafo del proyecto para orientarte.

- Rúbrica: [`RUBRICA_APF3.md`](RUBRICA_APF3.md). Para el 20/20 hay que estar en «Sobresaliente» en los cinco criterios.
- Análisis de brechas y diseño de cada pieza: [`PLAN_APF3.md`](PLAN_APF3.md).
- Descripción general del proyecto: [`DOCUMENTO_INFORMATIVO.md`](DOCUMENTO_INFORMATIVO.md) y [`ESTADO.md`](ESTADO.md).

## 1. Tablero (estado al 2026-11-20)

Marca cada casilla cuando esté fusionada en `develop` con pruebas verdes.

### Criterio 2 — IA y búsqueda
- [x] BFS, DFS, A\* y Hill Climbing (con reinicios) — `kiosk-api/src/kiosk/busqueda/algoritmos.py`
- [x] Espacio de estados del flujo W1–W4 (usa el `Checkout` real) y de «qué hay en la bandeja» por peso — `busqueda/problemas.py`
- [x] Pruebas (23, 99 % de cobertura del módulo) — `kiosk-api/tests/test_busqueda.py`
- [x] Demo comparativa: `cd kiosk-api && python -m kiosk.busqueda --peso 238`
- [x] Documento `docs/BUSQUEDA.md`: modelado formal (estado inicial, acciones, transición, meta, coste), tabla de resultados y cuándo usar cada algoritmo
- [x] Hill Climbing aplicado a afinar los umbrales con datos reales: `python -m kiosk.busqueda --umbral …/pares.csv` (`BUSQUEDA.md` §2.3)

### Criterio 3 — Regresión y clasificación
- [x] Datos medidos: huellas de las 107 fotos, 214 pares conocido/desconocido y 405 mediciones de latencia (`ml/src/mltools/apf3/datos.py`)
- [x] Regresión lineal (latencia de DINOv2 según lado e hilos) con R², RMSE, MAE
- [x] Regresión no lineal (polinómica, Ridge/Lasso) comparada con la lineal, con validación anidada
- [x] Regresión logística «conocido o desconocido» con accuracy, precisión, recall, F1, ROC-AUC, matriz de confusión (validada por producto)
- [x] Explicar cuándo se usa regresión y cuándo clasificación (`ml/MODELOS_APF3.md` §2)

### Criterio 4 — SVM, KNN, DT, Boosting
- [x] KNN, SVM (lineal y RBF), árbol de decisión, AdaBoost, Gradient Boosting y Random Forest sobre el mismo dataset
- [x] Validación cruzada estratificada anidada y búsqueda de hiperparámetros (`GridSearchCV`)
- [x] Tabla comparativa (accuracy, F1 macro, tiempos) y argumento de ensambles frente a modelos individuales (`ml/MODELOS_APF3.md` §5)

### Criterio 1 — Cloud y DevOps
- [x] Dockerfile de `kiosk-api`, `mock-gateway` y `kiosk-ui` y `docker-compose.yml` (probado en local con `ops/smoke_compose.py`)
- [x] Job `docker` en el CI: construye, levanta el stack y recorre una compra completa
- [x] Workflow de CD (`.github/workflows/cd.yml`): publica las imágenes en GHCR y despliega la pasarela en Render (`render.yaml`). La UI se queda en el quiosco (edge), ver el documento
- [x] `docs/CLOUD_DEVOPS.md`: Cloud (IaaS/PaaS/SaaS), DevOps, CI/CD, edge frente a cloud y diagramas
- [ ] **Equipo:** crear la cuenta de Render y el servicio desde `render.yaml`, y poner `RENDER_DEPLOY_HOOK_URL` y `PASARELA_URL` en GitHub (pasos en `CLOUD_DEVOPS.md` §6.3)
- [ ] Primer despliegue real y captura de pantalla para el informe (después de fusionar en `main`)

### Criterio 5 — Sustentación y código
- [x] `docs/TRADEOFFS.md`: ventajas, desventajas y coste de cada algoritmo y modelo
- [x] Guion de sustentación: `docs/SUSTENTACION.md`
- [x] Limpieza final: `ruff`, `mypy` y toda la suite en verde (2026-11-20: API 431 pruebas, 95,7 %; UI 140; ML 47)

## 2. Bloqueos conocidos

- **Las fotos de los productos no están en git** (`ml/data/` está ignorado). La carpeta de Drive no se pudo bajar de forma automática: Drive limita las descargas. Hay que bajarla desde el navegador como ZIP y descomprimirla en `ml/data/raw/`, con una carpeta por SKU (`ml/data/raw/CANCUN-33/…`). Mientras tanto, los criterios 3 y 4 solo pueden probarse con datos simulados, y deben marcarse así.
- **Render y el CD no se han ejecutado todavía**: el CD corre al fusionar en `main` y Render necesita una cuenta del equipo. Docker y compose sí se probaron en local (2026-11-19).
- **Fecha de entrega y proveedor de nube**: los decide el equipo.

## 3. Cómo usar el grafo (graphify)

El grafo del proyecto está en `graphify-out/`:

| Archivo | Para qué |
|---|---|
| `GRAPH_REPORT.md` | Resumen: conceptos centrales, conexiones sorprendentes, preguntas sugeridas. Las comunidades «TAREAS Criterio N» agrupan lo pendiente de cada criterio |
| `graph.html` | Grafo interactivo: ábrelo en el navegador, haz clic en los nodos y busca |
| `graph.json` | Datos del grafo para consultas |

**Consultar con Claude Code** (instala una vez: `pip install graphifyy` o `uv tool install graphifyy`, luego `graphify install`):

```
/graphify query "qué falta para el criterio 4"
/graphify query "cómo se relaciona la búsqueda A* con el peso de la bandeja"
/graphify path "FlujoCompra" "Checkout"
/graphify explain "PesoBandeja"
```

**Después de cambiar código o documentos**, actualiza el grafo (solo re-procesa lo nuevo) y súbelo en el mismo commit:

```
/graphify . --update
```

No hace falta clave de API. El código se analiza sin IA; los documentos los lee la propia sesión de Claude.

## 4. Reglas de trabajo

- Una rama por criterio (`feature/apf3-...`), PR hacia `develop`. El CI debe pasar: ruff, mypy, bandit, cobertura ≥ 90 %.
- Todo algoritmo nuevo lleva pruebas y docstrings. La rúbrica pide código limpio, optimizado y documentado.
- Si algo no se midió o se simuló, se dice (en el código y en el informe). No se inventan resultados.
