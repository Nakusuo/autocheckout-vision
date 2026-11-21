# Criterio 2: Fundamentos de IA y búsqueda

Código: `kiosk-api/src/kiosk/busqueda/` (`algoritmos.py`: BFS, DFS, A*, Hill Climbing y Hill
Climbing con reinicios; `problemas.py`: los tres problemas). Pruebas: `kiosk-api/tests/test_busqueda.py`.
Todos los números de este documento se midieron el 2026-11-20 en la laptop de desarrollo con:

```bash
cd kiosk-api
python -m kiosk.busqueda --peso 238          # flujo W1–W4 y «qué hay en la bandeja»
python -m kiosk.busqueda --umbral ../ml/data/apf3/pares.csv   # umbrales del reconocedor
```

## 1. Tres problemas del quiosco como espacios de estados

### 1.1 Flujo de compra (búsqueda no informada e informada)

| Elemento | Definición |
|---|---|
| Estado | (pantalla, unidades en el carrito). Pantallas: W1 inicio, W2 escaneo, W3 confirmar, QR pago, W4 ticket, fuera de servicio |
| Estado inicial | (W1, 0) |
| Acciones | iniciar, agregar, quitar, confirmar, corregir, pagar, pago_ok, pago_vencido, cancelar, falla, recuperar |
| Transición | **la máquina de estados real** (`kiosk.checkout.Checkout`): si el código del quiosco cambia, el espacio cambia con él. Una acción no permitida no genera sucesor |
| Meta | pantalla W4 (compra pagada) |
| Costo | 1 por acción |
| Heurística (A*) | pasos mínimos que faltan hasta W4 desde cada pantalla (5, 3, 2, 1, 0). Es **admisible**: nunca sobreestima, porque cada pantalla necesita al menos esas acciones |

Sirve para **verificar el diseño**: hay 20 estados alcanzables y **ninguno sin salida** (desde
cualquier pantalla se puede volver a terminar una compra o al inicio).

### 1.2 ¿Qué hay en la bandeja? (subconjuntos por peso)

| Elemento | Definición |
|---|---|
| Estado | multiconjunto ordenado de SKU (lo que se supone que hay en la bandeja) |
| Estado inicial | bandeja vacía |
| Acciones | agregar un producto del catálogo (11 productos) |
| Meta | el peso total está a ±5 g del peso medido (tolerancia del SRS, ON-02) |
| Costo | 1 por producto: la solución óptima es la que explica el peso con **menos** productos |
| Heurística (A*) | ⌈(peso que falta − 5 g) / peso del producto más pesado⌉: admisible |
| Búsqueda local | estado = una combinación completa; vecinos = cambiar, agregar o quitar un producto; objetivo = −|peso − medido| |

### 1.3 Umbrales del reconocedor (optimización con datos reales)

| Elemento | Definición |
|---|---|
| Estado | (umbral de parecido, margen) en una rejilla de 51 × 31 = **1581** pares (0,80–1,80 y 0,00–0,30) |
| Vecinos | los 8 pares de alrededor (un paso en uno o en los dos) |
| Objetivo | **F1** de «producto conocido» en 214 casos medidos con las 107 fotos (cada foto: una vez con su producto en la galería y otra sin él) |
| Datos | `ml/data/apf3/pares.csv`, generado por `python -m mltools.apf3 informe` |

## 2. Resultados

### 2.1 Flujo de compra

| Algoritmo | Costo de la solución | Expandidos | Generados | Frontera máx. | ¿Óptimo? |
|---|---|---|---|---|---|
| BFS | 5 | 11 | 16 | 6 | Sí |
| DFS | 7 | 9 | 16 | 8 | **No** (agrega 3 productos antes de confirmar) |
| A* | 5 | **5** | 9 | 4 | Sí |

A* expande menos de la mitad que BFS porque la heurística le dice qué pantalla está más cerca de
W4. DFS encuentra *una* compra, no la más corta.

### 2.2 ¿Qué hay en la bandeja?

| Peso medido | BFS (exp./gen.) | DFS (exp./gen.) | A* (exp./gen.) | Solución |
|---|---|---|---|---|
| 238 g | 2 / 23 | 77 / 88 | 10 / 53 | Cancún + Yofresh (2 productos) |
| 75 g | 2 / 13 | 2 / 23 | 9 / 41 | 2 × Cancún |
| 3170 g | 13 / 85 | 9 / 34 | 58 / 265 | 3 productos (con KR Piña) |

| Hill Climbing (3170 g) | Error | Evaluaciones |
|---|---|---|
| Un ascenso | 2 g | 121 |
| 10 reinicios | 1 g | 964 |

**Lectura crítica:** aquí A* expande **más** que BFS. La heurística divide por el producto más
pesado (KR Piña, 3100 g): para pesos chicos estima casi 0 y no guía. Es admisible pero poco
informada. Con soluciones de 2–3 productos el árbol es poco profundo y BFS llega rápido. A* convendría
con bandejas de muchos productos o una heurística más ajustada (p. ej., dividir por el peso del
producto más pesado *que aún cabe*). Además, varias combinaciones caen dentro de ±5 g (Casino +
Club Social o Chocman + Morochas para 75 g): el peso solo no identifica los productos, por eso el
quiosco confía en la cámara y usa el peso solo para validar.

### 2.3 Umbrales del reconocedor con Hill Climbing

| Método | Parecido ≥ | Margen ≥ | F1 | Evaluaciones |
|---|---|---|---|---|
| Regla de hoy (medida a mano) | 1,20 | 0,05 | 0,779 | — |
| Hill Climbing desde la regla de hoy | 1,22 | 0,04 | **0,785** | **17** |
| Hill Climbing, 10 reinicios al azar | 1,18 | 0,07 | 0,778 | 542 |
| Búsqueda exhaustiva | 1,22 | 0,04 | 0,785 | 1581 |
| **Fuera de muestra** (ajusta sin un producto, prueba con él) | | | regla fija **0,779** · HC 0,761 | |

- Hill Climbing desde un buen punto llega al **óptimo global** (el mismo que la exhaustiva) con
  ~1 % de las evaluaciones.
- Los reinicios al azar no lo garantizan: el F1 es **escalonado** (con 214 casos cambia de a
  saltos) y tiene mesetas donde ningún vecino mejora. Desde un punto lejano el ascenso se detiene
  en una meseta.
- **Decisión:** no se cambia la regla. Ajustada con todos los datos mejora 0,006, pero fuera de
  muestra empeora (0,761 frente a 0,779): esa mejora era sobreajuste. Con 107 fotos, la regla
  1,2 / 0,05 ya está prácticamente en el óptimo.

## 3. Cuándo usar cada algoritmo (en este proyecto)

| Algoritmo | Cuándo | Por qué |
|---|---|---|
| **BFS** | Espacios chicos con costo uniforme y soluciones poco profundas (flujo, bandejas de 2–3 productos) | Óptimo con costo 1; memoria O(b^d), aceptable aquí |
| **DFS** | Solo para saber si *existe* un camino (p. ej., verificar que no hay estados sin salida) | Poca memoria, pero no da la solución más corta |
| **A\*** | Cuando hay una heurística informativa (el flujo: pasos hasta W4) | Óptimo y expande menos; si la heurística es pobre (peso), no gana |
| **Hill Climbing** | Optimizar un valor sin una «meta» exacta (umbrales, combinación más cercana a un peso) | Barato; cae en óptimos locales y mesetas |
| **HC con reinicios** | Cuando no hay un buen punto de partida | Reduce el riesgo de óptimo local a cambio de más evaluaciones |
