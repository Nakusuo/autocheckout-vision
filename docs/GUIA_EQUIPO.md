# Guía del equipo — cómo llegar a la máxima nota (APF 3)

Léela primero. Dice qué falta, quién puede tomarlo y cómo usar el grafo del proyecto para orientarte.

- Rúbrica: [`RUBRICA_APF3.md`](RUBRICA_APF3.md). Para el 20/20 hay que estar en «Sobresaliente» en los cinco criterios.
- Análisis de brechas y diseño de cada pieza: [`PLAN_APF3.md`](PLAN_APF3.md).
- Descripción general del proyecto: [`DOCUMENTO_INFORMATIVO.md`](DOCUMENTO_INFORMATIVO.md) y [`ESTADO.md`](ESTADO.md).

## 1. Tablero (estado al 2026-11-16)

Marca cada casilla cuando esté fusionada en `develop` con pruebas verdes.

### Criterio 2 — IA y búsqueda
- [x] BFS, DFS, A\* y Hill Climbing (con reinicios) — `kiosk-api/src/kiosk/busqueda/algoritmos.py`
- [x] Espacio de estados del flujo W1–W4 (usa el `Checkout` real) y de «qué hay en la bandeja» por peso — `busqueda/problemas.py`
- [x] Pruebas (23, 99 % de cobertura del módulo) — `kiosk-api/tests/test_busqueda.py`
- [x] Demo comparativa: `cd kiosk-api && python -m kiosk.busqueda --peso 238`
- [ ] Documento `docs/BUSQUEDA.md`: modelado formal (estado inicial, acciones, transición, meta, coste), tabla de resultados y cuándo usar cada algoritmo
- [ ] Hill Climbing aplicado a afinar `KIOSK_THRESHOLD` con datos reales (depende del dataset)

### Criterio 3 — Regresión y clasificación
- [ ] Dataset tabular desde las fotos (`ml/data/raw/<SKU>/`) y el catálogo
- [ ] Regresión lineal (peso a partir del tamaño) con R², RMSE, MAE
- [ ] Regresión no lineal (polinómica, Ridge/Lasso) comparada con la lineal
- [ ] Regresión logística «conocido o desconocido» con accuracy, precisión, recall, F1, ROC-AUC, matriz de confusión
- [ ] Explicar cuándo se usa regresión y cuándo clasificación

### Criterio 4 — SVM, KNN, DT, Boosting
- [ ] KNN, SVM (lineal y RBF), árbol de decisión, boosting y Random Forest sobre el mismo dataset
- [ ] Validación cruzada estratificada y búsqueda de hiperparámetros (`GridSearchCV`)
- [ ] Tabla comparativa (accuracy, F1 macro, tiempos) y argumento de ensambles frente a modelos individuales

### Criterio 1 — Cloud y DevOps
- [ ] Dockerfile de `kiosk-api`, `mock-gateway` y `kiosk-ui` y `docker-compose.yml`
- [ ] Workflow de CD: publicar imágenes en GHCR y desplegar la pasarela y la UI en Render
- [ ] `docs/CLOUD_DEVOPS.md`: Cloud (IaaS/PaaS/SaaS), DevOps, CI/CD, edge frente a cloud y diagrama de arquitectura

### Criterio 5 — Sustentación y código
- [ ] `docs/TRADEOFFS.md`: ventajas, desventajas y coste de cada algoritmo y modelo
- [ ] Guion de sustentación (problema, modelado, resultados, trade-offs, limitaciones)
- [ ] Limpieza final: `ruff`, `mypy` y toda la suite en verde

## 2. Bloqueos conocidos

- **Las fotos de los productos no están en git** (`ml/data/` está ignorado). La carpeta de Drive no se pudo bajar de forma automática: Drive limita las descargas. Hay que bajarla desde el navegador como ZIP y descomprimirla en `ml/data/raw/`, con una carpeta por SKU (`ml/data/raw/CANCUN-33/…`). Mientras tanto, los criterios 3 y 4 solo pueden probarse con datos simulados, y deben marcarse así.
- **No hay Docker instalado** en el equipo donde se escribió el código de CD, así que esos archivos no se han probado.
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
