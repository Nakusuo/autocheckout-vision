# Trade-offs de cada algoritmo, modelo y decisión (criterio 5)

Cada fila dice qué se gana, qué se pierde y qué se eligió **con qué evidencia**. Los números
vienen de [`BUSQUEDA.md`](BUSQUEDA.md), [`ml/MODELOS_APF3.md`](ml/MODELOS_APF3.md) y
[`ml/reconocimiento.md`](ml/reconocimiento.md); lo no medido se marca como tal.

## 1. Búsqueda (criterio 2)

| Algoritmo | Gana | Pierde | En el proyecto |
|---|---|---|---|
| BFS | Óptimo con costo uniforme; simple | Memoria O(b^d): crece rápido con la profundidad | Flujo W1–W4: costo 5, 11 expandidos |
| DFS | Memoria O(b·d) | No óptimo (flujo: costo 7 en vez de 5); puede perderse en ramas largas | Útil solo para saber si existe un camino |
| A* | Óptimo y expande menos **si la heurística informa** | Hay que diseñar una heurística admisible; si es pobre, expande más que BFS | Flujo: 5 expandidos (vs 11). Peso: 58 vs 13 (heurística débil) |
| Hill Climbing | Barato: 17 evaluaciones para el óptimo de umbrales (vs 1581) | Óptimos locales y mesetas; depende del punto de partida | Umbrales: llega al óptimo desde la regla actual |
| HC con reinicios | Menos dependencia del inicio | 10× evaluaciones; no garantiza el óptimo | Umbrales: 542 evaluaciones y quedó en meseta (F1 0,778) |

## 2. Regresión y clasificación (criterio 3)

| Modelo | Gana | Pierde | Evidencia y decisión |
|---|---|---|---|
| Regresión lineal | Interpretable (ms por píxel), sin hiperparámetros | No capta la curva lado² ni los rendimientos decrecientes de los hilos | RMSE 18,6 ms, R² 0,886 |
| Polinómica (grado 4) | Capta la curva: error a la mitad | Puede sobreajustar y extrapola mal fuera del rango medido (70–224 px) | RMSE 10,3 ms, R² 0,964. **Elegida** para predecir el lado que cumple 150 ms |
| Ridge / Lasso | Controlan el sobreajuste; Lasso elimina términos | Un hiperparámetro más | La validación eligió α mínimo: con 405 mediciones y 2 variables no hacía falta |
| Regla fija (umbral) | Sin dependencias, transparente, se afinó con estos datos | Sin probabilidad; umbral rígido | F1 0,779. **Se queda en el quiosco** |
| Regresión logística | Probabilidad calibrable y mejor ROC-AUC (0,855); muestra que el margen pesa más | Con corte 0,5, F1 un poco menor (0,763) | Alternativa si se necesita una probabilidad |

## 3. Clasificadores (criterio 4)

| Modelo | Gana | Pierde | Evidencia |
|---|---|---|---|
| **SVM lineal** | El mejor F1 macro (0,791), 0,06 ms por foto, regulariza bien con pocos datos | Reentrenar para cada producto nuevo; no dice «no lo conozco» | Mejor opción si el catálogo es fijo |
| SVM RBF | Fronteras curvas | Dos hiperparámetros (C, γ) sensibles; aquí no supera al lineal | F1 0,746 |
| KNN (k = 1, coseno) | Sin entrenamiento: un producto nuevo se suma con sus fotos (lo que hace el quiosco) | Sensible a fotos atípicas; predice comparando con toda la galería | F1 0,757; el reconocedor real (top-2, varias vistas) mide 85 % |
| Árbol de decisión | Explicable, el más rápido (0,02 ms) | Varianza alta: corta de a una variable en 456 dimensiones | F1 0,434 |
| Random Forest | Baja la varianza del árbol (+0,13 F1) | 300 árboles: 4,5 ms por foto y 4,7 s para entrenar | F1 0,566 |
| Gradient Boosting | Baja el sesgo: el mejor de los árboles | El más lento de entrenar (31 s); más hiperparámetros | F1 0,677 |
| AdaBoost | Simple de ajustar | Con 4 fotos por clase persigue casos difíciles: no mejora al árbol | F1 0,402 |

## 4. Decisiones de sistema

| Decisión | Alternativa descartada | Por qué |
|---|---|---|
| Reconocer por **parecido con una galería** (DINOv2 + color) | Entrenar YOLOv8 por producto | 107 fotos no alcanzan para entrenar un detector; la galería admite productos nuevos sin reentrenar |
| **Recuadro guía** en la pantalla | Segmentar el producto del fondo (U²-Net) | El recorte va directo a la huella, ~100 ms; segmentar tardaba >1 s por cuadro |
| DINOv2 a **140 px** con 4 hilos | 224 px | 224 px: 86 % frente a 85 % de acierto, pero ~2,5× más lento. La regresión dice que 210 px aún cumple, pero sin margen |
| **Margen** además del umbral | Solo umbral de parecido | La logística le da más peso al margen; sin él se confundían Casino y Cancún |
| Agregar solo tras **3 cuadros iguales** | Botón «Agregar» | Más rápido para el cliente; un parpadeo no agrega nada. Costo: ~1,2 s por producto en local |
| Inferencia en el **borde** (PC/quiosco) | Inferencia en la nube | RNF-01 (≤ 150 ms) y RNF-03 (operar sin internet). Medido: por internet ~0,5–0,9 s por cuadro frente a 0,13 s en local |
| Pago por **QR propio + notificación** | Pasarela (Mercado Pago / Izipay) | Sin comisión ni contrato; riesgo: un pago ajeno del mismo monto (mitigable con montos únicos). La app de notificaciones **no existe todavía** |
| Publicar con un **túnel de Cloudflare** desde la PC | Cloud Run (listo en código) / Hugging Face Spaces | HF ya no da Docker gratis; Google rechazó la tarjeta (OR_BACR2_59). El túnel es gratis y sin tarjeta, pero depende de la PC encendida |
| **Sin balanza** (`KIOSK_SCALE=off`) | Validar el peso (ON-02) | No hay hardware. Un producto que no pasa por la cámara no se detecta: la alerta de seguridad es la mitigación. ON-02 queda «no medido» |
| Una sola copia del servidor | Varias copias | El estado de la compra y las alertas está en memoria: con varias copias se repartirían |
