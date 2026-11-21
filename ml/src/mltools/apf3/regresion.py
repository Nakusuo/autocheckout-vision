"""Criterio 3: regresión lineal y no lineal, y regresión logística, con datos medidos.

- **Regresión** (valor continuo): ¿cuántos ms tarda DINOv2 según el lado de la imagen y los hilos?
  Sirve para elegir el lado que cumple el RNF-01 (≤ 150 ms). El costo crece con los píxeles
  (lado²) y no baja en proporción a los hilos: una recta no alcanza, una polinómica sí.
- **Clasificación** (categoría): ¿el producto del recuadro está en el catálogo? La regresión
  logística aprende la frontera a partir del parecido y el margen, y da una probabilidad; se
  compara con la regla fija que usa hoy el reconocedor (parecido ≥ 1,2 y margen ≥ 0,05).

Todo con validación cruzada anidada: los hiperparámetros (grado, alfa, C) se eligen dentro de
cada partición de entrenamiento y las métricas salen de datos que el modelo no vio.
"""

from dataclasses import dataclass, field

import numpy as np
from sklearn.base import BaseEstimator, ClassifierMixin
from sklearn.linear_model import Lasso, LinearRegression, LogisticRegression, Ridge
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    mean_absolute_error,
    precision_score,
    r2_score,
    recall_score,
    roc_auc_score,
    root_mean_squared_error,
)
from sklearn.model_selection import GridSearchCV, GroupKFold, KFold, cross_val_predict
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import PolynomialFeatures, StandardScaler

# Regla fija del reconocedor hoy (kiosk.recognizer: BOX_THRESHOLD, BOX_MARGIN)
UMBRAL_PARECIDO = 1.2
UMBRAL_MARGEN = 0.05


@dataclass
class ResultadoRegresion:
    """Métricas fuera de muestra (media y desviación entre particiones) y la elección final."""

    r2: tuple[float, float]
    rmse: tuple[float, float]
    mae: tuple[float, float]
    mejores: dict = field(default_factory=dict)  # hiperparámetros elegidos con todos los datos


def modelos_regresion(rapido: bool = False) -> dict[str, GridSearchCV | object]:
    """Modelos a comparar. Las rejillas son los hiperparámetros que se eligen por validación."""
    grados = [2, 3] if rapido else [2, 3, 4]
    alfas = [0.1, 1.0] if rapido else [0.001, 0.01, 0.1, 1.0, 10.0]
    interno = KFold(3, shuffle=True, random_state=0)

    def polinomica(regresor) -> object:
        return make_pipeline(PolynomialFeatures(include_bias=False), StandardScaler(), regresor)

    return {
        "Lineal": make_pipeline(StandardScaler(), LinearRegression()),
        "Polinómica": GridSearchCV(
            polinomica(LinearRegression()),
            {"polynomialfeatures__degree": grados},
            cv=interno,
            scoring="neg_root_mean_squared_error",
        ),
        "Polinómica + Ridge": GridSearchCV(
            polinomica(Ridge()),
            {"polynomialfeatures__degree": grados, "ridge__alpha": alfas},
            cv=interno,
            scoring="neg_root_mean_squared_error",
        ),
        "Polinómica + Lasso": GridSearchCV(
            polinomica(Lasso(max_iter=500_000)),
            {"polynomialfeatures__degree": grados, "lasso__alpha": alfas},
            cv=interno,
            scoring="neg_root_mean_squared_error",
        ),
    }


def _media(valores: list[float]) -> tuple[float, float]:
    return float(np.mean(valores)), float(np.std(valores))


def comparar_regresiones(
    x: np.ndarray, y: np.ndarray, particiones: int = 5, rapido: bool = False
) -> dict[str, ResultadoRegresion]:
    """Valida cada modelo con `particiones` y devuelve R², RMSE y MAE fuera de muestra."""
    externo = KFold(particiones, shuffle=True, random_state=0)
    resultados = {}
    for nombre, modelo in modelos_regresion(rapido).items():
        r2, rmse, mae = [], [], []
        for entreno, prueba in externo.split(x):
            modelo.fit(x[entreno], y[entreno])
            pred = modelo.predict(x[prueba])
            r2.append(r2_score(y[prueba], pred))
            rmse.append(root_mean_squared_error(y[prueba], pred))
            mae.append(mean_absolute_error(y[prueba], pred))
        modelo.fit(x, y)
        mejores = dict(modelo.best_params_) if isinstance(modelo, GridSearchCV) else {}
        resultados[nombre] = ResultadoRegresion(_media(r2), _media(rmse), _media(mae), mejores)
    return resultados


def lado_maximo(modelo, hilos: int, objetivo_ms: float, lados=range(56, 449, 14)) -> int | None:
    """Mayor lado (múltiplo de 14, como pide DINOv2) que según el modelo cumple `objetivo_ms`."""
    candidatos = [lado for lado in lados if modelo.predict([[lado, hilos]])[0] <= objetivo_ms]
    return max(candidatos) if candidatos else None


class ReglaFija(BaseEstimator, ClassifierMixin):
    """La regla de hoy como clasificador: conocido si parecido ≥ umbral y margen ≥ margen."""

    def __init__(self, umbral: float = UMBRAL_PARECIDO, margen: float = UMBRAL_MARGEN):
        self.umbral = umbral
        self.margen = margen

    def fit(self, x, y):
        """No aprende nada: los umbrales son fijos."""
        self.classes_ = np.array([0, 1])
        return self

    def predict(self, x):
        """1 (conocido) si cumple los dos umbrales."""
        x = np.asarray(x)
        return ((x[:, 0] >= self.umbral) & (x[:, 1] >= self.margen)).astype(int)


@dataclass
class ResultadoClasificacion:
    """Métricas con las predicciones fuera de muestra de todas las particiones juntas."""

    accuracy: float
    precision: float
    recall: float
    f1: float
    roc_auc: float
    matriz: list[list[int]]  # [[VN, FP], [FN, VP]]; positivo = conocido
    mejores: dict = field(default_factory=dict)
    coeficientes: dict = field(default_factory=dict)


def _metricas(y, pred, puntaje, mejores=None, coeficientes=None) -> ResultadoClasificacion:
    return ResultadoClasificacion(
        float(accuracy_score(y, pred)),
        float(precision_score(y, pred, zero_division=0)),
        float(recall_score(y, pred, zero_division=0)),
        float(f1_score(y, pred, zero_division=0)),
        float(roc_auc_score(y, puntaje)),
        confusion_matrix(y, pred, labels=[0, 1]).tolist(),
        mejores or {},
        coeficientes or {},
    )


def comparar_logistica(
    x: np.ndarray, y: np.ndarray, grupos: np.ndarray, particiones: int = 5
) -> dict[str, ResultadoClasificacion]:
    """Regla fija frente a regresión logística, validando por producto (GroupKFold).

    El ROC-AUC de la regla usa el parecido como puntaje; el de la logística, su probabilidad.
    """
    externo = GroupKFold(min(particiones, len(np.unique(grupos))))
    regla = ReglaFija()
    pred_regla = regla.predict(x)
    resultados = {"Regla fija (hoy)": _metricas(y, pred_regla, x[:, 0])}

    logistica = GridSearchCV(
        make_pipeline(StandardScaler(), LogisticRegression(max_iter=5_000)),
        {"logisticregression__C": [0.01, 0.1, 1.0, 10.0, 100.0]},
        cv=3,
        scoring="f1",
    )
    prob = cross_val_predict(
        logistica, x, y, groups=grupos, cv=externo, method="predict_proba"
    )[:, 1]
    logistica.fit(x, y)
    final = logistica.best_estimator_
    escala, lineal = final.named_steps["standardscaler"], final.named_steps["logisticregression"]
    nombres = ["parecido", "margen", "segundo"]
    coef = {n: float(c) for n, c in zip(nombres, lineal.coef_[0] / escala.scale_, strict=True)}
    coef["intercepto"] = float(lineal.intercept_[0] - (lineal.coef_[0] * escala.mean_ / escala.scale_).sum())
    resultados["Regresión logística"] = _metricas(
        y, (prob >= 0.5).astype(int), prob, dict(logistica.best_params_), coef
    )
    return resultados
