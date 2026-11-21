"""Modelos APF3 con datos sintéticos pequeños (el CI no tiene las fotos ni los modelos)."""

import json

import numpy as np
import pytest

from mltools.apf3 import clasificacion, regresion
from mltools.apf3.__main__ import main
from mltools.apf3.datos import (
    EMBED_DIMS,
    TablaProductos,
    medir_latencia,
    pares_conocido,
    tabla_productos,
)


def galeria_falsa(ruta, productos=4, fotos=6, dims=EMBED_DIMS + 8, semilla=0):
    """Galería del recuadro con la misma forma que la real: 4 vistas × 4 rotaciones por foto."""
    rng = np.random.default_rng(semilla)
    centros = rng.standard_normal((productos, dims))
    vectores, etiquetas, ids, vistas = [], [], [], []
    foto = 0
    for p in range(productos):
        for _ in range(fotos):
            base = centros[p] + 0.3 * rng.standard_normal(dims)
            for vista in ("seg", "c45", "c60", "c80"):
                for _rot in range(4):
                    v = base + 0.05 * rng.standard_normal(dims)
                    vectores.append(v / np.linalg.norm(v))
                    etiquetas.append(f"SKU-{p}")
                    ids.append(foto)
                    vistas.append(vista)
            foto += 1
    np.savez(
        ruta,
        vectors=np.array(vectores, np.float32),
        labels=np.array(etiquetas),
        photos=np.array(ids),
        views=np.array(vistas),
    )
    return ruta


def latencia_falsa(ruta, semilla=0):
    """ms ≈ lado² / hilos^0.7 + ruido: no lineal, como DINOv2."""
    rng = np.random.default_rng(semilla)
    filas = []
    for hilos in (1, 2, 4):
        for lado in range(70, 225, 14):
            for _ in range(3):
                ms = 0.004 * lado**2 / hilos**0.7 + 5 + rng.normal(0, 1)
                filas.append((lado, hilos, ms))
    np.savetxt(ruta, filas, delimiter=",", header="lado,hilos,ms", comments="")
    return ruta


def test_tabla_productos_toma_una_fila_por_foto(tmp_path):
    tabla = tabla_productos(galeria_falsa(tmp_path / "g.npz"))
    assert tabla.huellas.shape == (24, EMBED_DIMS + 8)
    assert tabla.dinov2.shape[1] == EMBED_DIMS and tabla.color.shape[1] == 8
    assert sorted(set(tabla.skus)) == ["SKU-0", "SKU-1", "SKU-2", "SKU-3"]


def test_tabla_productos_exige_galeria_del_recuadro(tmp_path):
    np.savez(tmp_path / "vieja.npz", vectors=np.zeros((2, 3)), labels=np.array(["a", "b"]))
    with pytest.raises(ValueError, match="views"):
        tabla_productos(tmp_path / "vieja.npz")
    galeria_falsa(tmp_path / "g.npz")
    with pytest.raises(ValueError, match="vista"):
        tabla_productos(tmp_path / "g.npz", vista="c99")


def test_pares_conocido_da_un_caso_de_cada_clase_por_foto():
    rng = np.random.default_rng(1)
    centros = rng.standard_normal((3, 5))
    huellas = np.vstack([centros[i % 3] + 0.1 * rng.standard_normal(5) for i in range(9)])
    huellas /= np.linalg.norm(huellas, axis=1, keepdims=True)
    tabla = TablaProductos(huellas, np.array([f"P{i % 3}" for i in range(9)]))
    x, y, grupos = pares_conocido(tabla)
    assert x.shape == (18, 3) and y.tolist() == [1, 0] * 9
    assert list(grupos[:2]) == ["P0", "P0"]
    conocidos, desconocidos = x[y == 1], x[y == 0]
    assert conocidos[:, 0].mean() > desconocidos[:, 0].mean()  # con su producto se parece más
    assert np.allclose(x[:, 1], x[:, 0] - x[:, 2])  # margen = mejor − segundo


def test_medir_latencia_cuenta_cada_combinacion():
    tiempo = iter(range(1000))
    x, y = medir_latencia(
        lambda lado, hilos: lambda: None, [10, 20], [1, 2], repeticiones=3, reloj=lambda: next(tiempo)
    )
    assert x.shape == (12, 2) and np.allclose(y, 1000.0)  # cada medición: 1 «segundo» del reloj falso
    assert {tuple(f) for f in x} == {(10, 1), (20, 1), (10, 2), (20, 2)}


def test_regresion_polinomica_gana_a_la_lineal_si_hay_curva(tmp_path):
    datos = np.loadtxt(latencia_falsa(tmp_path / "l.csv"), delimiter=",", skiprows=1)
    res = regresion.comparar_regresiones(datos[:, :2], datos[:, 2], particiones=3, rapido=True)
    assert res["Polinómica"].rmse[0] < res["Lineal"].rmse[0]
    assert res["Polinómica"].r2[0] > 0.95
    assert "polynomialfeatures__degree" in res["Polinómica"].mejores
    modelo = regresion.modelos_regresion(True)["Polinómica"].fit(datos[:, :2], datos[:, 2])
    lado = regresion.lado_maximo(modelo, hilos=1, objetivo_ms=80)
    assert lado is not None and lado % 14 == 0 and modelo.predict([[lado, 1]])[0] <= 80
    assert regresion.lado_maximo(modelo, hilos=1, objetivo_ms=-1) is None


def test_regla_fija_y_logistica():
    regla = regresion.ReglaFija().fit(None, None)
    assert regla.predict([[1.3, 0.1, 1.2], [1.3, 0.01, 1.29], [1.0, 0.5, 0.5]]).tolist() == [1, 0, 0]
    rng = np.random.default_rng(2)
    n = 60
    conocidos = np.column_stack([rng.normal(1.5, 0.1, n), rng.normal(0.3, 0.05, n)])
    desconocidos = np.column_stack([rng.normal(1.0, 0.1, n), rng.normal(0.05, 0.03, n)])
    x2 = np.vstack([conocidos, desconocidos])
    x = np.column_stack([x2, x2[:, 0] - x2[:, 1]])
    y = np.array([1] * n + [0] * n)
    grupos = np.array([f"G{i % 6}" for i in range(2 * n)])
    res = regresion.comparar_logistica(x, y, grupos, particiones=3)
    log = res["Regresión logística"]
    assert log.roc_auc > 0.95 and log.f1 > 0.9
    assert set(log.coeficientes) == {"parecido", "margen", "segundo", "intercepto"}
    assert sum(map(sum, res["Regla fija (hoy)"].matriz)) == 2 * n


def test_clasificadores_comparan_individuales_y_ensambles():
    rng = np.random.default_rng(3)
    centros = rng.standard_normal((3, 6)) * 3
    x = np.vstack([centros[i % 3] + rng.standard_normal(6) for i in range(36)])
    y = np.array([f"P{i % 3}" for i in range(36)])
    res = clasificacion.comparar(x, y, particiones=3, rapido=True)
    assert set(res) == {
        "KNN", "SVM lineal", "SVM RBF", "Árbol de decisión", "Random Forest", "AdaBoost",
        "Gradient Boosting",
    }
    assert {r.familia for r in res.values()} == {clasificacion.INDIVIDUAL, clasificacion.ENSAMBLE}
    assert res["SVM lineal"].accuracy[0] > 0.8
    assert all(0 <= r.f1_macro[0] <= 1 and r.predecir_ms >= 0 for r in res.values())
    assert "n_neighbors" in res["KNN"].mejores


def test_cli_informe_y_errores(tmp_path, capsys):
    galeria = galeria_falsa(tmp_path / "g.npz", productos=3, fotos=6)
    latencia = latencia_falsa(tmp_path / "l.csv")
    salida = tmp_path / "apf3" / "resultados.json"
    argv = ["informe", "--galeria", str(galeria), "--latencia", str(latencia)]
    assert main([*argv, "--salida", str(salida), "--rapido"]) == 0
    texto = capsys.readouterr().out
    assert "## Regresión" in texto and "## Clasificadores" in texto and "ROC-AUC" in texto
    datos = json.loads(salida.read_text())
    assert datos["n"]["fotos"] == 18 and set(datos["lado_maximo_150ms"]) == {"1", "2", "4"}
    pares = (salida.parent / "pares.csv").read_text().splitlines()
    assert pares[0] == "parecido,margen,conocido,sku" and len(pares) == 1 + 2 * 18
    with pytest.raises(SystemExit):
        main(["informe", "--galeria", str(tmp_path / "no.npz"), "--latencia", str(latencia)])
    with pytest.raises(SystemExit):
        main(["latencia", "--modelo", str(tmp_path / "no.onnx")])
