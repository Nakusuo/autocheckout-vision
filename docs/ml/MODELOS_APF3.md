# Criterios 3 y 4: regresión, clasificación logística y SVM, KNN, árboles y boosting

Código: `ml/src/mltools/apf3/` (`datos.py`, `regresion.py`, `clasificacion.py`). Pruebas:
`ml/tests/test_apf3.py` (con datos sintéticos, para el CI). Todos los números de este documento
se **midieron** el 2026-11-20 con los datos del proyecto; nada es simulado.

```bash
cd ml && pip install -e ".[apf3,bench]"
python -m mltools.apf3 latencia   # 405 mediciones de DINOv2 → data/apf3/latencia.csv (~3 min)
python -m mltools.apf3 informe    # todos los modelos → data/apf3/resultados.json (~3 min)
```

## 1. Datos

| Conjunto | Origen | Tamaño |
|---|---|---|
| **Fotos de productos** | `ml/data/raw/<SKU>/` (Drive del equipo), 11 productos, **de 4 a 20 fotos por producto** (desbalanceado) | 107 fotos |
| **Huella por foto** | Recuadro central al 60 % (lo que ve la cámara del navegador), sacado de la galería `galeria-recuadro.npz`: 384 valores de **DINOv2** (forma) + 72 de **color** (tono × saturación) | 107 × 456 |
| **Pares conocido/desconocido** | Cada foto, comparada con las demás: con su producto en la galería (debe aceptarse) y sin él (debe rechazarse) | 214 casos (balanceado) |
| **Latencia** | ms de DINOv2 en onnxruntime, en esta laptop, para 9 lados de imagen (70–224 px) × 1, 2 y 4 hilos × 15 repeticiones | 405 mediciones |

## 2. Cuándo regresión y cuándo clasificación

- **Regresión** cuando la respuesta es un **número continuo**: ¿cuántos milisegundos tarda el
  reconocedor con una imagen de cierto lado? Se mide con R², RMSE y MAE (en ms).
- **Clasificación** cuando la respuesta es una **categoría**: ¿el producto está en el catálogo
  (sí/no)? ¿cuál de los 11 productos es? Se mide con accuracy, precisión, recall, F1, ROC-AUC y la
  matriz de confusión.
- La **regresión logística** es un modelo de **clasificación** aunque se llame «regresión»:
  ajusta una curva logística que da la **probabilidad** de la clase, y se decide con un umbral.

## 3. Criterio 3a: regresión lineal y no lineal (latencia de DINOv2)

**Para qué:** elegir el tamaño de imagen que cumple el RNF-01 (≤ 150 ms por cuadro) sin probar a
ciegas. Variables: lado de la imagen (px) e hilos de CPU. Validación cruzada anidada: 5
particiones externas para medir, y dentro de cada una se eligen grado y α con 3 particiones.

| Modelo | R² | RMSE (ms) | MAE (ms) | Hiperparámetros elegidos |
|---|---|---|---|---|
| Lineal | 0,886 ± 0,017 | 18,6 ± 2,4 | 13,2 ± 1,1 | — |
| Polinómica | **0,964 ± 0,019** | **10,3 ± 3,3** | **5,6 ± 0,9** | grado 4 |
| Polinómica + Ridge | 0,964 ± 0,018 | 10,3 ± 3,2 | 5,6 ± 0,9 | grado 4, α = 0,001 |
| Polinómica + Lasso | 0,964 ± 0,019 | 10,3 ± 3,3 | 5,6 ± 0,9 | grado 4, α = 0,001 |

**Interpretación**

- La recta se equivoca en ~19 ms de media: no puede representar que el costo crece con los
  **píxeles** (lado²) ni que agregar hilos rinde cada vez menos. La polinómica baja el error a la
  mitad (RMSE 10 ms, R² 0,96).
- **Regularización:** la validación eligió el α más chico. Con 2 variables y 405 mediciones el
  modelo no sobreajusta, así que Ridge y Lasso no aportan; se probaron y se descartaron con datos,
  no por suposición.
- **Uso:** según el modelo, el lado máximo que cumple 150 ms es **168 px con 1 hilo y 210 px con 2
  o 4 hilos**. El quiosco usa **140 px con 4 hilos**: deja margen para el resto del cuadro
  (decodificar, recortar, comparar) y para equipos más lentos. A 224 px el acierto sube poco
  (86 % frente a 85 %, ver `reconocimiento.md`) y el reconocimiento tarda ~2,5 veces más.

## 4. Criterio 3b: regresión logística, ¿producto conocido o desconocido?

**Para qué:** hoy el reconocedor acepta un producto si el parecido es ≥ 1,2 y le saca ≥ 0,05 al
segundo (regla fija, medida a mano). La logística aprende la frontera con los datos y da una
probabilidad. Validación **por producto** (GroupKFold, 5 particiones): un producto nunca está a la
vez en entrenamiento y en prueba, como pasaría con un producto nuevo. C se elige dentro (3
particiones).

| Modelo | Accuracy | Precisión | Recall | F1 | ROC-AUC | Matriz [[VN, FP], [FN, VP]] |
|---|---|---|---|---|---|---|
| Regla fija (hoy) | **0,785** | **0,802** | **0,757** | **0,779** | 0,826 | [[87, 20], [26, 81]] |
| Regresión logística (C = 100) | 0,771 | 0,790 | 0,738 | 0,763 | **0,855** | [[86, 21], [28, 79]] |

Modelo aprendido: P(conocido) = σ(7,13·parecido + 11,21·margen − 0,32·segundo − 9,80).

**Interpretación**

- **El margen pesa más que el parecido** (11,2 frente a 7,1 por unidad): lo que delata a un
  producto desconocido no es que se parezca poco, sino que se parece *parecido* a dos productos.
  Confirma con datos la decisión del margen (sin él se confundían Casino y Cancún).
- El ROC-AUC de la logística es mayor (0,855 frente a 0,826): **ordena mejor** los casos por
  probabilidad. Pero con el corte en 0,5 su F1 queda un poco debajo de la regla, que se afinó
  con estas mismas fotos.
- Los **errores que importan**: 20–21 falsos positivos de 107 (un producto que no está en el
  catálogo se tomaría por otro y se cobraría mal). Para un quiosco real convendría subir el corte
  de probabilidad a cambio de más rechazos, que solo piden repetir el producto.
- **Decisión:** el quiosco sigue con la regla (mejor F1 y sin dependencias). La logística queda
  como alternativa si se quiere una probabilidad o un corte ajustable. El ajuste de los umbrales
  con Hill Climbing está en `docs/BUSQUEDA.md` §2.3.

## 5. Criterio 4: SVM, KNN, árbol de decisión, Random Forest y boosting (¿qué producto es?)

Mismos datos (107 × 456) y misma evaluación para todos: validación cruzada **estratificada anidada**
(4 particiones externas, porque el producto con menos fotos tiene 4; 3 internas con
`GridSearchCV`). F1 **macro** porque las clases están desbalanceadas: cuenta igual un producto
con 4 fotos que uno con 20.

| Modelo | Tipo | Accuracy | F1 macro | Entrenar (s) | Predecir (ms/foto) | Hiperparámetros elegidos |
|---|---|---|---|---|---|---|
| **SVM lineal** | individual | **0,851 ± 0,082** | **0,791 ± 0,107** | 0,14 | 0,06 | C = 0,01 |
| KNN | individual | 0,795 ± 0,065 | 0,757 ± 0,085 | 0,90 | 0,17 | k = 1, coseno |
| SVM RBF | individual | 0,833 ± 0,084 | 0,746 ± 0,098 | 0,23 | 0,08 | C = 10, γ = 0,001 |
| Gradient Boosting | ensamble | 0,766 ± 0,109 | 0,677 ± 0,163 | 31,26 | 0,84 | 100 árboles, prof. 3, η = 0,1 |
| Random Forest | ensamble | 0,758 ± 0,083 | 0,566 ± 0,092 | 4,70 | 4,47 | 300 árboles, 10 % de variables |
| Árbol de decisión | individual | 0,495 ± 0,086 | 0,434 ± 0,126 | 0,23 | 0,02 | prof. 10, hoja ≥ 2 |
| AdaBoost | ensamble | 0,561 ± 0,091 | 0,402 ± 0,074 | 8,91 | 1,57 | 200 árboles prof. 2, η = 1 |

### 5.1 Ensambles frente a modelos individuales

- **Frente al árbol solo, los ensambles ganan mucho:** el árbol de decisión acierta la mitad (F1
  0,43). Con 107 fotos y 456 variables, cada corte se ajusta a detalles de unas pocas fotos
  (**varianza alta**).
  - **Random Forest** (bagging: 300 árboles con muestras y variables al azar, y votación) sube a
    0,566, porque **promediar baja la varianza**.
  - **Gradient Boosting** (árboles chicos en serie, cada uno corrige el error del anterior) sube a
    0,677, porque **baja el sesgo**.
- **AdaBoost** no mejora al árbol: repondera las fotos mal clasificadas, y con 4 fotos por clase
  termina persiguiendo casos difíciles o ruidosos.
- **Pero el mejor modelo no es un ensamble.** Las huellas de DINOv2 ya están hechas para que
  productos distintos queden en zonas separables. Un **SVM lineal** (una frontera por clase, con un
  margen amplio y C chico, es decir, mucha regularización) aprovecha eso mejor que cortes de a una
  variable, que es lo que hacen los árboles.
- **Conclusión:** los ensambles corrigen los defectos de los árboles (varianza o sesgo), pero no
  cambian que un árbol no es el modelo adecuado para estas variables. Elegir el modelo según la
  forma de los datos importa más que ensamblar.

### 5.2 Relación con el reconocedor del quiosco

- El reconocedor actual (galería + parecido, ver `reconocimiento.md`) equivale a un **KNN** con
  coseno que promedia las 2 huellas más parecidas. Mide 85 % con su propia evaluación (cada foto
  fuera, con varias vistas y rotaciones en la galería). El KNN de esta tabla, con una sola vista
  por foto, da 79,5 %.
- El **SVM lineal** alcanza 85,1 % y predice en 0,06 ms, muy por debajo del RNF-01. El tiempo
  total sigue dominado por DINOv2 (~100 ms).
- **Por qué el quiosco sigue con la galería:** se agrega un producto nuevo sin reentrenar (basta
  con sumar sus fotos), y el umbral permite decir «no lo conozco», cosa que un SVM entrenado con 11
  clases no hace por sí solo. Si el catálogo se fija, un SVM sobre las mismas huellas es la mejora
  más barata.

## 6. Limitaciones (decirlas en la sustentación)

- **Pocos datos:** 107 fotos y entre 4 y 20 por producto. Las desviaciones entre particiones son
  grandes (±0,08–0,16): las diferencias chicas entre modelos (SVM lineal frente a RBF) no son
  concluyentes.
- **Fotos del Drive**, no de la cámara de la demo. Con fotos de la misma webcam el acierto
  debería subir (pendiente: `kiosk.recognizer capturar`).
- **Latencia medida en una sola laptop.** En otro equipo hay que volver a medir: el modelo es el
  mismo, los números cambian.
- Los casos «desconocido» son productos del catálogo que se quitan de la galería, no productos de
  verdad ajenos a la tienda.
