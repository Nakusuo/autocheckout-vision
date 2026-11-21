"""Corre los modelos de la rúbrica APF3 y muestra las tablas (criterios 3 y 4).

    python -m mltools.apf3 latencia   # mide DINOv2 por lado e hilos → ml/data/apf3/latencia.csv
    python -m mltools.apf3 informe    # regresión, logística y clasificadores → resultados.json

Requiere la galería del recuadro (`python -m kiosk.recognizer galeria --recuadro`) y, para la
latencia, el modelo DINOv2 y el extra `bench` (onnxruntime). Nada se simula: si falta un archivo,
el comando lo dice y termina.
"""

import argparse
import json
from dataclasses import asdict
from pathlib import Path

import numpy as np

from mltools.apf3 import clasificacion, regresion
from mltools.apf3.datos import inferencia_dinov2, medir_latencia, pares_conocido, tabla_productos
from mltools.console import utf8_output

DATA = Path(__file__).resolve().parents[3] / "data"
MODELOS = DATA / "models"
SALIDA = DATA / "apf3"
LADOS = (70, 84, 98, 112, 126, 140, 168, 196, 224)
HILOS = (1, 2, 4)
OBJETIVO_MS = 150.0  # RNF-01


def _f(par: tuple[float, float], d: int = 3) -> str:
    return f"{par[0]:.{d}f} ± {par[1]:.{d}f}"


def informe(galeria: Path, latencia: Path, salida: Path, rapido: bool = False) -> dict:
    """Corre todo, imprime las tablas en Markdown y guarda los números en `salida`."""
    datos = np.loadtxt(latencia, delimiter=",", skiprows=1)
    x_lat, y_lat = datos[:, :2], datos[:, 2]
    tabla = tabla_productos(galeria)
    x_par, y_par, grupos = pares_conocido(tabla)
    # Para Hill Climbing del criterio 2 (python -m kiosk.busqueda --umbral …/pares.csv)
    with salida.with_name("pares.csv").open("w", encoding="utf-8") as f:
        f.write("parecido,margen,conocido,sku\n")
        for (mejor, margen, _), etiqueta, sku in zip(x_par, y_par, grupos, strict=True):
            f.write(f"{mejor:.6f},{margen:.6f},{int(etiqueta)},{sku}\n")

    reg = regresion.comparar_regresiones(x_lat, y_lat, rapido=rapido)
    log = regresion.comparar_logistica(x_par, y_par, grupos)
    cla = clasificacion.comparar(tabla.huellas, tabla.skus, rapido=rapido)

    mejor_reg = min(reg, key=lambda n: reg[n].rmse[0])
    modelo = regresion.modelos_regresion(rapido)[mejor_reg].fit(x_lat, y_lat)
    lados = {h: regresion.lado_maximo(modelo, h, OBJETIVO_MS) for h in HILOS}

    print(f"## Regresión: ms por imagen de DINOv2 ({len(y_lat)} mediciones)\n")
    print("| Modelo | R² | RMSE (ms) | MAE (ms) | Hiperparámetros |\n|---|---|---|---|---|")
    for n, r in reg.items():
        print(f"| {n} | {_f(r.r2)} | {_f(r.rmse, 1)} | {_f(r.mae, 1)} | {r.mejores or '—'} |")
    print(f"\nCon {mejor_reg}, lado máximo para ≤ {OBJETIVO_MS:.0f} ms: {lados}\n")

    print(f"## Clasificación logística: ¿producto conocido? ({len(y_par)} casos)\n")
    print("| Modelo | Accuracy | Precisión | Recall | F1 | ROC-AUC | Matriz [[VN,FP],[FN,VP]] |")
    print("|---|---|---|---|---|---|---|")
    for n, r in log.items():
        print(
            f"| {n} | {r.accuracy:.3f} | {r.precision:.3f} | {r.recall:.3f} | {r.f1:.3f} "
            f"| {r.roc_auc:.3f} | {r.matriz} |"
        )
    print(f"\nLogística: {log['Regresión logística'].mejores} · {log['Regresión logística'].coeficientes}\n")

    print(f"## Clasificadores: ¿qué producto es? ({len(tabla.skus)} fotos, 11 productos)\n")
    print("| Modelo | Tipo | Accuracy | F1 macro | Entrenar (s) | Predecir (ms/foto) | Hiperparámetros |")
    print("|---|---|---|---|---|---|---|")
    for n, r in sorted(cla.items(), key=lambda kv: -kv[1].f1_macro[0]):
        print(
            f"| {n} | {r.familia} | {_f(r.accuracy)} | {_f(r.f1_macro)} | {r.entrenar_s:.2f} "
            f"| {r.predecir_ms:.3f} | {r.mejores} |"
        )
    resultado = {
        "regresion": {n: asdict(r) for n, r in reg.items()},
        "lado_maximo_150ms": {str(h): v for h, v in lados.items()},
        "logistica": {n: asdict(r) for n, r in log.items()},
        "clasificadores": {n: asdict(r) for n, r in cla.items()},
        "n": {"latencia": len(y_lat), "pares": len(y_par), "fotos": len(tabla.skus)},
    }
    salida.write_text(json.dumps(resultado, indent=2, ensure_ascii=False, default=str))
    print(f"\nGuardado en {salida}")
    return resultado


def main(argv: list[str] | None = None) -> int:
    """Punto de entrada de la línea de comandos."""
    utf8_output()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    lat = sub.add_parser("latencia", help="mide DINOv2 por lado e hilos")
    lat.add_argument("--modelo", type=Path, default=MODELOS / "dinov2-small.onnx")
    lat.add_argument("--repeticiones", type=int, default=15)
    lat.add_argument("--salida", type=Path, default=SALIDA / "latencia.csv")
    inf = sub.add_parser("informe", help="regresión, logística y clasificadores")
    inf.add_argument("--galeria", type=Path, default=MODELOS / "galeria-recuadro.npz")
    inf.add_argument("--latencia", type=Path, default=SALIDA / "latencia.csv")
    inf.add_argument("--salida", type=Path, default=SALIDA / "resultados.json")
    inf.add_argument("--rapido", action="store_true", help="rejillas chicas (prueba rápida)")
    args = parser.parse_args(argv)

    if args.cmd == "latencia":
        if not args.modelo.is_file():
            parser.exit(1, f"No está el modelo {args.modelo} (ver docs/ml/reconocimiento.md)\n")
        args.salida.parent.mkdir(parents=True, exist_ok=True)
        x, y = medir_latencia(inferencia_dinov2(args.modelo), LADOS, HILOS, args.repeticiones)
        np.savetxt(args.salida, np.column_stack([x, y]), delimiter=",", header="lado,hilos,ms",
                   comments="", fmt=["%d", "%d", "%.3f"])
        print(f"{len(y)} mediciones guardadas en {args.salida}")
        return 0
    for archivo in (args.galeria, args.latencia):
        if not archivo.is_file():
            parser.exit(1, f"Falta {archivo}: corre primero «latencia» y la galería del recuadro\n")
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    informe(args.galeria, args.latencia, args.salida, args.rapido)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
