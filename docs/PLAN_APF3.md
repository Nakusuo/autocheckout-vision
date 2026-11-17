# Plan APF 3 — qué falta según la rúbrica

Curso: Innovación y Transformación Digital (UTP). Rúbrica: «Avance del Proyecto Final 3». Se evalúa de 1 a 4 puntos en cinco criterios, máximo 20.

Base del análisis: grafo de código de graphify (105 archivos, 1183 nodos) más una búsqueda de cada tema de la rúbrica en el repositorio. Las notas «hoy» son una estimación mía, no la nota real.

## 1. Resumen

| # | Criterio | Qué hay hoy | Nota estimada hoy | Qué falta |
|---|---|---|---|---|
| 1 | Cloud & DevOps | CI en GitHub Actions con 6 jobs (ruff, mypy, bandit, pytest, vitest, e2e, gitleaks), Dependabot y mutación semanal. **No hay CD, ni Docker, ni cloud, ni justificación escrita** | 2 | Despliegue (CD), contenedores y un documento que explique Cloud, DevOps, CI/CD y edge frente a cloud |
| 2 | Fundamentos de IA y Búsqueda | Solo la máquina de estados W1–W4. **No hay BFS, DFS, A\* ni Hill Climbing** | 1 | Modelar el problema como espacio de estados e implementar los cuatro algoritmos |
| 3 | Regresión y clasificación | Ninguno. El reconocimiento actual es similitud por embeddings (DINOv2 + color) con umbral fijado a mano (`KIOSK_THRESHOLD`) | 1 | Regresión lineal, no lineal y logística, con métricas e hiperparámetros |
| 4 | SVM, KNN, DT, Boosting | Ninguno con `scikit-learn`. La galería es en la práctica un vecino más cercano (1-NN), pero no está medida ni comparada | 1 | Los cuatro modelos, validación cruzada y comparación contra un ensamble |
| 5 | Sustentación y código | Código limpio, probado (cobertura 96 %) y documentado | 3 | Análisis de trade-offs y un guion de sustentación |

Total estimado hoy: **8 de 20**. Meta: 16 o más. La infraestructura de calidad del repositorio ya sirve de base. Lo que falta es el contenido de IA y la parte de nube.

## 2. Principios del plan

- Todo debe colgar del problema real (el quiosco). Así no queda como ejercicio suelto y se puede defender en la sustentación.
- Cada pieza lleva código en `ml/` o `kiosk-api/`, pruebas (el repositorio exige cobertura ≥ 90 %), un documento corto en `docs/` y una tabla de resultados.
- No se inventan datos. Si el dataset es pequeño, se dice así y se reporta con validación cruzada.

## 3. Trabajo por criterio

### Criterio 2 — Búsqueda (mayor brecha, hacerlo primero)

**Espacio de estados 1: la máquina de compra W1–W4**
- Estados: W1, W2, W3, QR, W4, Fuera de servicio. Operadores: iniciar, agregar, confirmar, corregir, pagar, cancelar, ayuda.
- **BFS** halla la compra más corta (menos acciones) de W1 a W4. **DFS** explora todos los caminos y detecta estados inalcanzables o sin salida.
- Archivo sugerido: `ml/src/mltools/busqueda/estados.py`. Se alimenta de las transiciones reales de `kiosk/checkout.py`, para que sea verificable.

**Espacio de estados 2: identificar qué hay en la bandeja a partir del peso** (solo tiene sentido con balanza)
- Estado: subconjunto de ≤ 3 productos del catálogo. Meta: peso total dentro de ±5 g del medido. Coste: número de productos.
- **A\*** con heurística admisible (por ejemplo, diferencia restante de peso dividida entre el peso máximo del catálogo). Se compara con BFS y DFS en nodos expandidos y tiempo.
- Con **Hill Climbing**: ajustar `KIOSK_THRESHOLD` y los tamaños de zona para maximizar los aciertos sobre la galería. Se muestra el problema de los máximos locales y se prueba con reinicios aleatorios.
- Documento: tabla BFS / DFS / A\* / Hill Climbing con completitud, optimalidad, memoria y cuándo usar cada uno.

### Criterio 3 — Regresión y clasificación logística

Dataset: tabla construida a partir de las fotos de `ml/data/raw/` y del catálogo (11 productos).

- **Regresión lineal**: predecir el peso a partir del área de la caja detectada (bbox) o del tamaño en píxeles. Métricas: R², RMSE, MAE.
- **Regresión no lineal** (polinómica grado 2–3 o regresión con kernel): misma tarea, comparada con la lineal. Se justifica el grado con validación cruzada. Regularización Ridge/Lasso como hiperparámetro.
- **Regresión logística**: clasificar «producto conocido o desconocido» a partir de la similitud con la galería. Sustituye al umbral manual por uno aprendido y da probabilidades. Métricas: accuracy, precisión, recall, F1, ROC-AUC, matriz de confusión.
- Se explica en el documento cuándo se usa regresión (valor continuo: peso) y cuándo clasificación (categoría: conocido o desconocido).

### Criterio 4 — SVM, KNN, Árboles de decisión y Boosting

- Tarea: clasificar el SKU de los 11 productos a partir de los embeddings del reconocedor o de características de color.
- Modelos: **KNN** (varios `k` y métricas de distancia), **SVM** (kernel lineal y RBF, `C` y `gamma`), **Árbol de decisión** (profundidad), **Boosting** (`GradientBoosting` o `AdaBoost`) y un **Random Forest** como ensamble por bagging.
- Comparación con la misma partición y validación cruzada estratificada, `GridSearchCV` para hiperparámetros. Se reporta accuracy, F1 macro, tiempo de entrenamiento y de inferencia (el RNF-01 exige ≤ 150 ms).
- Argumento: ensambles frente a modelos individuales (sesgo y varianza), con los números medidos.
- Archivo sugerido: `ml/src/mltools/modelos.py` y un cuaderno `ml/notebooks/comparacion.ipynb` con las gráficas.

### Criterio 1 — Cloud y DevOps

**Hacer (código y configuración)**
1. **Dockerfile** para `kiosk-api`, `mock-gateway` y `kiosk-ui`, más un `docker-compose.yml` que levante los tres servicios.
2. **CD**: un workflow que, al fusionar en `main`, construya y publique las imágenes (GHCR) y despliegue `mock-gateway` y la UI en un servicio gratuito o de estudiante. La elección del proveedor la decide el equipo.
3. Ampliar el CI actual: `docker build` como job y, si aplica, un entorno de pruebas (staging).

**Documentar (`docs/CLOUD_DEVOPS.md`)**
- Qué es Cloud Computing (IaaS, PaaS, SaaS) y dónde cae cada pieza del proyecto.
- **Edge frente a cloud**: la inferencia debe quedar en el quiosco (RNF-01 de 150 ms y RNF-03 de operación sin internet). En la nube van la pasarela de pagos, el catálogo central, las métricas y las alertas.
- DevOps: ciclo plan, código, CI, CD, operación y monitoreo. Qué practica ya el proyecto (Dependabot, gitleaks, mutación semanal, cobertura mínima) y por qué CI/CD reduce el riesgo.
- Diagrama de arquitectura con las zonas edge y cloud.

### Criterio 5 — Sustentación y código

- `docs/TRADEOFFS.md`: tabla por algoritmo con ventajas, desventajas, coste y cuándo conviene.
- Guion de sustentación: problema, modelado, resultados, trade-offs y limitaciones (dataset de 56 fotos, sin balanza).
- Antes de entregar: `ruff`, `mypy` y la suite verdes. Vale la pena arreglar los 15 avisos menores de ruff que ya detecté.

## 4. Orden sugerido

| Fase | Entrega | Criterio |
|---|---|---|
| 1 | Dockerfiles + compose + workflow de CD + `CLOUD_DEVOPS.md` | 1 |
| 2 | BFS, DFS, A\*, Hill Climbing con pruebas y tabla comparativa | 2 |
| 3 | Dataset tabular y regresiones (lineal, no lineal, logística) | 3 |
| 4 | SVM, KNN, DT, Boosting, Random Forest con validación cruzada | 4 |
| 5 | `TRADEOFFS.md`, cuaderno, guion de sustentación, limpieza final | 5 |

Las fases 3 y 4 comparten el dataset, así que conviene construirlo una sola vez.

## 5. Riesgos y decisiones abiertas

- **Dataset pequeño**: 56 fotos de 11 productos. Es suficiente para comparar modelos con validación cruzada, pero no para afirmar que generalizan. Hay que decirlo en la sustentación. Tomar más fotos con la webcam mejora todo.
- **Balanza**: sin balanza, el problema de A\* con pesos es un experimento sobre el catálogo y no un flujo real. Debe presentarse así.
- **Dependencias nuevas**: `scikit-learn` y `numpy`. Entran como extra de `ml/` para no tocar el quiosco.
- **Proveedor de nube** y **fecha de entrega**: las decide el equipo. Este plan no asume ninguno.
- Los documentos de la rúbrica piden código «limpio, optimizado y documentado». Eso incluye docstrings y pruebas de cada algoritmo nuevo.
