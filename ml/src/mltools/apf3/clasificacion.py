"""Criterio 4: KNN, SVM, árbol de decisión, Random Forest y boosting sobre los mismos datos.

Tarea: reconocer cuál de los 11 productos es, a partir de la huella del recuadro (DINOv2 + color).
Todos los modelos se evalúan igual: validación cruzada estratificada anidada (externa de
`particiones`, interna de 3 para `GridSearchCV`), con accuracy, F1 macro (las clases están
desbalanceadas: de 4 a 20 fotos), tiempo de entrenamiento y ms por predicción (RNF-01: ≤ 150 ms).

Ensambles frente a modelos individuales:
- **Random Forest** (bagging) promedia muchos árboles entrenados con muestras y variables al azar:
  baja la varianza del árbol solo, que con 107 fotos y 456 variables sobreajusta.
- **Boosting** (AdaBoost, Gradient Boosting) encadena árboles chicos que corrigen los errores del
  anterior: baja el sesgo. Con pocos datos por clase puede sobreajustar igual; por eso se valida.
"""

import time
from collections import Counter
from dataclasses import dataclass

import numpy as np
from sklearn.ensemble import (
    AdaBoostClassifier,
    HistGradientBoostingClassifier,
    RandomForestClassifier,
)
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import GridSearchCV, StratifiedKFold
from sklearn.neighbors import KNeighborsClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC
from sklearn.tree import DecisionTreeClassifier

# Familia de cada modelo, para la tabla y el argumento de ensambles
INDIVIDUAL, ENSAMBLE = "individual", "ensamble"


def modelos(rapido: bool = False) -> dict[str, tuple[str, object, dict]]:
    """nombre → (familia, modelo, rejilla de hiperparámetros)."""
    r = rapido
    return {
        "KNN": (
            INDIVIDUAL,
            KNeighborsClassifier(),
            {
                "n_neighbors": [1, 3] if r else [1, 3, 5],
                "metric": ["cosine"] if r else ["cosine", "euclidean"],
                "weights": ["uniform", "distance"],
            },
        ),
        "SVM lineal": (
            INDIVIDUAL,
            make_pipeline(StandardScaler(), SVC(kernel="linear")),
            {"svc__C": [0.1, 1.0] if r else [0.01, 0.1, 1.0, 10.0]},
        ),
        "SVM RBF": (
            INDIVIDUAL,
            make_pipeline(StandardScaler(), SVC(kernel="rbf")),
            {
                "svc__C": [1.0, 10.0] if r else [1.0, 10.0, 100.0],
                "svc__gamma": ["scale"] if r else ["scale", 0.001, 0.01],
            },
        ),
        "Árbol de decisión": (
            INDIVIDUAL,
            DecisionTreeClassifier(random_state=0),
            {"max_depth": [3, None] if r else [3, 5, 10, None], "min_samples_leaf": [1, 2]},
        ),
        "Random Forest": (
            ENSAMBLE,
            RandomForestClassifier(random_state=0, n_jobs=-1),
            {
                "n_estimators": [50] if r else [100, 300],
                "max_features": ["sqrt"] if r else ["sqrt", 0.1],
            },
        ),
        "AdaBoost": (
            ENSAMBLE,
            AdaBoostClassifier(DecisionTreeClassifier(max_depth=2), random_state=0),
            {
                "n_estimators": [20] if r else [50, 200],
                "learning_rate": [0.5] if r else [0.1, 0.5, 1.0],
            },
        ),
        "Gradient Boosting": (
            ENSAMBLE,
            HistGradientBoostingClassifier(random_state=0),
            {
                "max_iter": [20] if r else [100, 200],
                "learning_rate": [0.1] if r else [0.05, 0.1],
                "max_depth": [3] if r else [3, None],
            },
        ),
    }


@dataclass
class Resultado:
    """Métricas fuera de muestra (media y desviación entre particiones) y costo."""

    familia: str
    accuracy: tuple[float, float]
    f1_macro: tuple[float, float]
    entrenar_s: float  # segundos por ajuste con la rejilla (media)
    predecir_ms: float  # ms por foto (media)
    mejores: dict  # hiperparámetros más elegidos en las particiones


def _mas_elegidos(elegidos: list[dict]) -> dict:
    """Los hiperparámetros que más particiones eligieron."""
    textos = [repr(sorted(e.items())) for e in elegidos]
    ganador = Counter(textos).most_common(1)[0][0]
    return elegidos[textos.index(ganador)]


def comparar(
    x: np.ndarray, y: np.ndarray, particiones: int = 4, rapido: bool = False
) -> dict[str, Resultado]:
    """Compara todos los modelos con la misma validación cruzada anidada."""
    # No más particiones que fotos tiene la clase más chica (en el dataset real: 4)
    particiones = min(particiones, int(np.unique(y, return_counts=True)[1].min()))
    externo = StratifiedKFold(particiones, shuffle=True, random_state=0)
    interno = StratifiedKFold(3, shuffle=True, random_state=0)
    resultados = {}
    for nombre, (familia, modelo, rejilla) in modelos(rapido).items():
        acc, f1, entrenar, predecir, elegidos = [], [], [], [], []
        for entreno, prueba in externo.split(x, y):
            busqueda = GridSearchCV(modelo, rejilla, cv=interno, scoring="f1_macro", n_jobs=-1)
            inicio = time.perf_counter()
            busqueda.fit(x[entreno], y[entreno])
            entrenar.append(time.perf_counter() - inicio)
            inicio = time.perf_counter()
            pred = busqueda.predict(x[prueba])
            predecir.append((time.perf_counter() - inicio) * 1000 / len(prueba))
            acc.append(accuracy_score(y[prueba], pred))
            f1.append(f1_score(y[prueba], pred, average="macro"))
            elegidos.append(busqueda.best_params_)
        resultados[nombre] = Resultado(
            familia,
            (float(np.mean(acc)), float(np.std(acc))),
            (float(np.mean(f1)), float(np.std(f1))),
            float(np.mean(entrenar)),
            float(np.mean(predecir)),
            _mas_elegidos(elegidos),
        )
    return resultados
