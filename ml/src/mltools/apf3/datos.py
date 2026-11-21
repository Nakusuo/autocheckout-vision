"""Datos para los modelos de la rúbrica APF3, todos medidos (nada simulado).

1. **Tabla de productos** (`tabla_productos`): una fila por foto de `ml/data/raw/`, sacada de la
   galería del recuadro (`python -m kiosk.recognizer galeria --recuadro`). Cada fila es la huella
   del recuadro central al 60 % (lo que ve la cámara del navegador): 384 valores de DINOv2 y 72 de
   color (tono × saturación). Etiqueta: el SKU.
2. **Pares conocido/desconocido** (`pares_conocido`): para cada foto se calcula el parecido con el
   resto, dos veces: con su producto en la galería (debe aceptarse) y sin él (un producto que el
   quiosco no conoce: debe rechazarse). Es lo que decide hoy el umbral fijo del reconocedor.
3. **Latencia** (`medir_latencia`): milisegundos por imagen de DINOv2 según el lado de la imagen y
   los hilos de CPU, medidos en esta máquina con onnxruntime.
"""

import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np

EMBED_DIMS = 384  # DINOv2-small: el resto de la huella es el histograma de color
VISTA = "c60"  # recuadro central al 60 %, la vista con la que se mide el reconocedor
TOP = 2  # el reconocedor promedia las 2 huellas más parecidas de cada producto


@dataclass(frozen=True)
class TablaProductos:
    """Una fila por foto: huella completa, sus dos partes y el SKU."""

    huellas: np.ndarray  # (n, 456) = [DINOv2, √peso·color], como las compara el reconocedor
    skus: np.ndarray  # (n,) etiqueta

    @property
    def dinov2(self) -> np.ndarray:
        """Solo la parte de forma (DINOv2)."""
        return self.huellas[:, :EMBED_DIMS]

    @property
    def color(self) -> np.ndarray:
        """Solo el histograma de color."""
        return self.huellas[:, EMBED_DIMS:]


def tabla_productos(galeria: Path, vista: str = VISTA) -> TablaProductos:
    """Lee la galería del recuadro y deja una fila por foto: la vista `vista` sin rotar."""
    with np.load(galeria, allow_pickle=False) as g:
        if "views" not in g.files:
            raise ValueError(f"{galeria} no es una galería del recuadro (falta «views»)")
        vectores, skus, fotos, vistas = g["vectors"], g["labels"], g["photos"], g["views"]
    filas = []
    for foto in np.unique(fotos):
        mias = np.flatnonzero((fotos == foto) & (vistas == vista))
        if len(mias):
            filas.append(int(mias[0]))  # la primera de las 4 rotaciones es la foto tal cual
    if not filas:
        raise ValueError(f"La galería no tiene la vista {vista!r}")
    return TablaProductos(vectores[filas].astype(np.float64), skus[filas].astype(str))


def _parecido_por_producto(
    parecidos: np.ndarray, skus: np.ndarray, excluir: str | None, top: int
) -> list[float]:
    """Parecido de una consulta con cada producto: promedio de sus `top` huellas más parecidas."""
    resultado = []
    for sku in np.unique(skus):
        if sku == excluir:
            continue
        valores = np.sort(parecidos[skus == sku])[::-1][:top]
        resultado.append(float(valores.mean()))
    return sorted(resultado, reverse=True)


def pares_conocido(
    tabla: TablaProductos, top: int = TOP
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(X, y, grupos) para «¿este producto está en el catálogo?».

    X = [mejor parecido, margen sobre el segundo, segundo parecido]; y = 1 conocido, 0 desconocido.
    Cada foto aporta un caso conocido (las demás fotos, sin ella misma) y uno desconocido (sin
    ninguna foto de su producto). `grupos` es el SKU: al validar por grupos, un producto nunca está
    a la vez en entrenamiento y en prueba.
    """
    x, y, grupos = [], [], []
    n = len(tabla.skus)
    for i in range(n):
        otros = np.arange(n) != i
        parecidos = tabla.huellas[otros] @ tabla.huellas[i]
        skus = tabla.skus[otros]
        for etiqueta, excluir in ((1, None), (0, str(tabla.skus[i]))):
            ranking = _parecido_por_producto(parecidos, skus, excluir, top)
            mejor = ranking[0]
            segundo = ranking[1] if len(ranking) > 1 else 0.0
            x.append([mejor, mejor - segundo, segundo])
            y.append(etiqueta)
            grupos.append(str(tabla.skus[i]))
    return np.array(x), np.array(y), np.array(grupos)


def medir_latencia(
    inferir: Callable[[int, int], Callable[[], object]],
    lados: Sequence[int],
    hilos: Sequence[int],
    repeticiones: int = 15,
    calentamiento: int = 3,
    reloj: Callable[[], float] = time.perf_counter,
) -> tuple[np.ndarray, np.ndarray]:
    """Mide ms por imagen para cada (lado, hilos). Devuelve X = [lado, hilos] e y = ms.

    `inferir(lado, hilos)` prepara el modelo y devuelve la función que procesa una imagen.
    """
    x, y = [], []
    for h in hilos:
        for lado in lados:
            correr = inferir(lado, h)
            for _ in range(calentamiento):
                correr()
            for _ in range(repeticiones):
                inicio = reloj()
                correr()
                x.append([lado, h])
                y.append((reloj() - inicio) * 1000)
    return np.array(x, dtype=np.float64), np.array(y)


def inferencia_dinov2(modelo: Path) -> Callable[[int, int], Callable[[], object]]:
    """`inferir(lado, hilos)` real: DINOv2 en onnxruntime con una imagen fija de ese lado."""
    import onnxruntime as ort

    def inferir(lado: int, hilos: int) -> Callable[[], object]:
        opciones = ort.SessionOptions()
        opciones.intra_op_num_threads = hilos
        opciones.add_session_config_entry("session.intra_op.allow_spinning", "0")
        sesion = ort.InferenceSession(str(modelo), opciones, providers=["CPUExecutionProvider"])
        entrada = sesion.get_inputs()[0].name
        imagen = np.random.default_rng(0).standard_normal((1, 3, lado, lado)).astype(np.float32)
        return lambda: sesion.run(None, {entrada: imagen})

    return inferir
