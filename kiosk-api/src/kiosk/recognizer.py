"""Reconocimiento por parecido (requiere el extra `vision`).

Con ~5 fotos por producto no alcanza para entrenar un detector, así que no se entrena nada:
1. Se recorta el producto y se pinta el fondo de gris (en la galería, con un modelo que quita
   el fondo; en el quiosco, comparando con la bandeja vacía, porque la cámara está fija).
2. Su «huella» une la descripción de DINOv2 (forma y estampado) con un histograma de color.
3. Se compara con la huella de cada foto de referencia (en 4 rotaciones: la cámara mira desde
   arriba y el producto puede estar girado). Si nada se parece lo suficiente: DESCONOCIDO.

Agregar un producto es agregar sus fotos y volver a generar la galería.

Dos formas de encontrar el producto en el cuadro (KIOSK_FONDO):
- «fijo» (por defecto): cámara cenital sobre una bandeja; lo que difiere de la bandeja vacía.
- «libre»: cualquier fondo (pantalla vertical, producto en la mano, a futuro el celular). Cada
  cuadro pasa por el mismo modelo que recorta las fotos de la galería (U²-Net «silueta»). Lo que
  no se parece a ningún producto no se suma ni genera alerta: la cámara ve personas y el cuarto.

Uso (las opciones --galeria y --embedder van antes del comando):
    python -m kiosk.recognizer galeria
    python -m kiosk.recognizer evaluar
    python -m kiosk.recognizer camara --camera 0
    python -m kiosk.recognizer capturar CANCUN-33 --camera 0   # fotos con la cámara de la demo
    python -m kiosk.recognizer medir                           # ms por cuadro (RNF-01: ≤ 150)
"""

import argparse
import logging
import threading
import time
from collections import Counter, deque
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from kiosk.vision import CameraSource, Detection, FrameSource, YoloOnnxDetector

REPO = Path(__file__).resolve().parents[3]
MODELS = REPO / "ml" / "data" / "models"
DEFAULT_EMBEDDER = MODELS / "dinov2-small.onnx"
DEFAULT_SEGMENTER = MODELS / "silueta.onnx"
DEFAULT_GALLERY = MODELS / "galeria.npz"
DEFAULT_BOX_GALLERY = MODELS / "galeria-recuadro.npz"  # «galeria --recuadro» (cámara del navegador)

log = logging.getLogger(__name__)

UNKNOWN = "DESCONOCIDO"
GRAY = 124
COLOR_WEIGHT = 0.5  # cuánto pesa el color frente a DINOv2 (afinado con las fotos del dataset)
# Parecido mínimo (máximo posible: 1 + COLOR_WEIGHT). Con el dataset, los aciertos dan ≥ 1,0; algo
# muy distinto (una mano sola) queda por debajo. Se ajusta con KIOSK_THRESHOLD mirando `camara`.
THRESHOLD = 0.95
IMAGE_EXT = {".jpg", ".jpeg", ".png"}
# Lado de la imagen que recibe DINOv2 (múltiplo de 14); se guarda en la galería. Con las fotos del
# dataset: 224 px → 91 % y ~250 ms; 140 px → 88–89 % y ~105 ms (cumple RNF-01, ≤ 150 ms).
EMBED_SIZE = 140
_MEAN = np.array([0.485, 0.456, 0.406], np.float32)
_STD = np.array([0.229, 0.224, 0.225], np.float32)


def imread(path: Path) -> np.ndarray | None:
    """cv2.imread no abre rutas con tildes o eñes en Windows."""
    return cv2.imdecode(np.fromfile(path, np.uint8), cv2.IMREAD_COLOR)


def _normalize(bgr: np.ndarray, size: int) -> np.ndarray:
    x = cv2.resize(bgr, (size, size), interpolation=cv2.INTER_AREA)
    x = (cv2.cvtColor(x, cv2.COLOR_BGR2RGB).astype(np.float32) / 255 - _MEAN) / _STD
    return x.transpose(2, 0, 1)


def isolate(
    bgr: np.ndarray, mask: np.ndarray, *, merge_components: bool = False
) -> tuple[np.ndarray, np.ndarray] | None:
    """Recorta la mancha principal (o los fragmentos ya agrupados), con fondo gris."""
    binary = (mask > 0.5).astype(np.uint8)
    n, _, stats, _ = cv2.connectedComponentsWithStats(binary)
    if n <= 1:
        return None
    if merge_components:
        x, y, w, h = cv2.boundingRect(binary)
    else:
        i = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
        x, y, w, h = stats[i, :4]
    pad = int(0.05 * max(w, h))
    rows, cols = bgr.shape[:2]
    x0, y0, x1, y1 = (
        max(0, x - pad),
        max(0, y - pad),
        min(cols, x + w + pad),
        min(rows, y + h + pad),
    )
    alpha = np.clip(mask[y0:y1, x0:x1], 0, 1)[..., None].astype(np.float32)
    patch = (bgr[y0:y1, x0:x1] * alpha + GRAY * (1 - alpha)).astype(np.uint8)
    side = max(patch.shape[:2])
    square = np.full((side, side, 3), GRAY, np.uint8)
    square_mask = np.zeros((side, side), np.uint8)
    top, left = (side - patch.shape[0]) // 2, (side - patch.shape[1]) // 2
    square[top : top + patch.shape[0], left : left + patch.shape[1]] = patch
    square_mask[top : top + patch.shape[0], left : left + patch.shape[1]] = alpha[..., 0] > 0.5
    return square, square_mask


def color_hist(crop: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Tono × saturación del producto (sin el fondo), normalizado."""
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    hist = cv2.calcHist([hsv], [0, 1], mask.astype(np.uint8), [18, 4], [0, 180, 0, 256]).flatten()
    hist = np.sqrt(hist)
    return hist / (np.linalg.norm(hist) + 1e-9)


class Embedder:
    """DINOv2 en ONNX: devuelve el token CLS normalizado de cada imagen."""

    def __init__(self, session, size: int = EMBED_SIZE):
        self._session = session
        self._input = session.get_inputs()[0].name
        self.size = size

    @classmethod
    def from_model(cls, path: Path = DEFAULT_EMBEDDER, size: int = EMBED_SIZE) -> "Embedder":
        import onnxruntime as ort

        options = ort.SessionOptions()
        options.intra_op_num_threads = 4  # el mejor en la laptop de desarrollo (8 núcleos)
        options.add_session_config_entry("session.intra_op.allow_spinning", "0")
        session = ort.InferenceSession(str(path), options, providers=["CPUExecutionProvider"])
        return cls(session, size)

    def __call__(self, images: list[np.ndarray]) -> np.ndarray:
        batch = np.stack([_normalize(im, self.size) for im in images])
        cls_tokens = self._session.run(None, {self._input: batch})[0][:, 0]
        return cls_tokens / np.linalg.norm(cls_tokens, axis=1, keepdims=True)


class Segmenter:
    """U²-Net (silueta/u2netp de rembg): separa el producto del fondo en las fotos de referencia."""

    def __init__(self, session):
        self._session = session
        self._input = session.get_inputs()[0].name

    @classmethod
    def from_model(cls, path: Path = DEFAULT_SEGMENTER) -> "Segmenter":
        import onnxruntime as ort

        options = ort.SessionOptions()
        options.intra_op_num_threads = 4
        options.add_session_config_entry("session.intra_op.allow_spinning", "0")
        return cls(ort.InferenceSession(str(path), options, providers=["CPUExecutionProvider"]))

    def __call__(self, bgr: np.ndarray) -> np.ndarray:
        out = self._session.run(None, {self._input: _normalize(bgr, 320)[None]})[0][0, 0]
        out = (out - out.min()) / (out.max() - out.min() + 1e-6)
        return cv2.resize(out, (bgr.shape[1], bgr.shape[0]))


def fingerprints(
    embed: Embedder,
    crop: np.ndarray,
    mask: np.ndarray,
    rotations: int = 1,
    color_weight: float = COLOR_WEIGHT,
) -> np.ndarray:
    """Huella = [DINOv2, √peso·color]: el producto punto suma ambos parecidos."""
    views = [crop] + [cv2.rotate(crop, r) for r in (0, 1, 2)[: rotations - 1]]
    shape = embed(views)
    color = np.sqrt(color_weight) * color_hist(crop, mask)
    return np.hstack([shape, np.tile(color, (len(views), 1))]).astype(np.float32)


@dataclass
class Gallery:
    vectors: np.ndarray  # (n, d)
    labels: np.ndarray  # (n,) SKU de cada huella
    photos: np.ndarray  # (n,) foto de origen (las 4 rotaciones comparten número)
    size: int = EMBED_SIZE  # el quiosco debe describir los cuadros con el mismo tamaño
    color_weight: float = COLOR_WEIGHT  # con el que se hicieron las huellas: la consulta lo repite
    top: int = 1  # parecido de un SKU = promedio de sus `top` huellas más parecidas
    # Vista de cada huella: «seg» (producto recortado) o «c60» (recuadro central del 60 %, etc.)
    views: np.ndarray | None = None
    threshold: float | None = None  # umbral y margen medidos para esta galería (si se midieron)
    margin: float | None = None

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        extra: dict[str, np.ndarray] = {}
        if self.views is not None:
            extra["views"] = self.views
        if self.threshold is not None:
            extra["threshold"] = np.array(self.threshold)
        if self.margin is not None:
            extra["margin"] = np.array(self.margin)
        np.savez_compressed(
            path,
            vectors=self.vectors,
            labels=self.labels,
            photos=self.photos,
            size=self.size,
            color_weight=self.color_weight,
            top=self.top,
            **extra,  # type: ignore[arg-type]  # numpy tipa mal los **kwargs de savez
        )

    @classmethod
    def load(cls, path: Path) -> "Gallery":
        with np.load(path, allow_pickle=False) as data:
            files = set(data.files)

            def value(key: str, default):
                return data[key].item() if key in files else default

            return cls(
                data["vectors"],
                data["labels"],
                data["photos"],
                int(value("size", 224)),
                float(value("color_weight", COLOR_WEIGHT)),
                int(value("top", 1)),
                data["views"] if "views" in files else None,
                value("threshold", None),
                value("margin", None),
            )

    def ranking(self, vector: np.ndarray, skip_photo: int | None = None) -> list[tuple[str, float]]:
        """Parecido por SKU (promedio de sus `top` huellas más parecidas), de mayor a menor.

        Con `top` > 1 un producto con muchas fotos no gana solo por tener una que se parezca
        por casualidad: necesita varias."""
        scores = self.vectors @ vector
        keep = self.photos != skip_photo if skip_photo is not None else slice(None)
        scores, labels = scores[keep], self.labels[keep]
        best: dict[str, float] = {}
        for label in np.unique(labels):
            mine = np.sort(scores[labels == label])[::-1][: self.top]
            best[str(label)] = float(mine.mean())
        return sorted(best.items(), key=lambda kv: -kv[1])


def center_crop(bgr: np.ndarray, fraction: float) -> np.ndarray:
    """Cuadrado central de lado `fraction` × el lado menor: lo que ve un recuadro guía."""
    rows, cols = bgr.shape[:2]
    side = max(1, int(fraction * min(rows, cols)))
    top, left = (rows - side) // 2, (cols - side) // 2
    return bgr[top : top + side, left : left + side]


def center_mask(side: int, fraction: float = 0.8) -> np.ndarray:
    """Círculo central: el color se mide donde está el producto, no en el fondo de las esquinas."""
    mask = np.zeros((side, side), np.uint8)
    cv2.circle(mask, (side // 2, side // 2), int(side * fraction / 2), 1, -1)
    return mask


def view_name(fraction: float) -> str:
    """Nombre de la vista de un recorte central en la galería: 0.45 → «c45»."""
    return f"c{round(fraction * 100)}"


def build_gallery(
    raw: Path,
    embed: Embedder,
    segment: Segmenter,
    skus: set[str] | None = None,
    crops: tuple[float, ...] = (),
    color_weight: float = COLOR_WEIGHT,
    top: int = 1,
) -> Gallery:
    """Galería con el producto recortado de cada foto (4 rotaciones). Con `crops`, suma además el
    recuadro central de cada foto en esos tamaños: así se ve lo que manda el navegador (producto
    con algo de fondo), y la consulta se parece a la galería."""
    vectors, labels, photos, views = [], [], [], []
    photo = 0
    folders = sorted(p for p in raw.iterdir() if p.is_dir() and (skus is None or p.name in skus))
    for folder in folders:
        for path in sorted(p for p in folder.iterdir() if p.suffix.lower() in IMAGE_EXT):
            image = imread(path)
            if image is None or (found := isolate(image, segment(image))) is None:
                print(f"  sin producto visible, se omite: {folder.name}/{path.name}")
                continue
            parts = [("seg", fingerprints(embed, *found, rotations=4, color_weight=color_weight))]
            for fraction in crops:
                box = center_crop(image, fraction)
                fp = fingerprints(
                    embed, box, center_mask(box.shape[0]), rotations=4, color_weight=color_weight
                )
                parts.append((view_name(fraction), fp))
            for name, fp in parts:
                vectors.append(fp)
                labels += [folder.name] * len(fp)
                photos += [photo] * len(fp)
                views += [name] * len(fp)
            photo += 1
    if not vectors:
        raise ValueError(f"No hay fotos en {raw}")
    size = getattr(embed, "size", EMBED_SIZE)
    return Gallery(
        np.vstack(vectors),
        np.array(labels),
        np.array(photos),
        size,
        color_weight,
        top,
        np.array(views) if crops else None,
    )


def leave_one_out(
    gallery: Gallery, query_view: str | None = None
) -> tuple[int, int, list[tuple[str, str, float]]]:
    """Reconoce cada foto (sin rotar) con las demás. Devuelve aciertos, total y fallos.

    `query_view` (p. ej. «c60»): la consulta es esa vista de la foto, como el recuadro guía."""
    hits, total, misses = 0, 0, []
    for photo in np.unique(gallery.photos):
        mine = gallery.photos == photo
        if query_view is not None and gallery.views is not None:
            mine &= gallery.views == query_view
        if not mine.any():
            continue
        i = int(np.flatnonzero(mine)[0])
        ranking = gallery.ranking(gallery.vectors[i], skip_photo=int(photo))
        truth, (guess, score) = str(gallery.labels[i]), ranking[0]
        total += 1
        if guess == truth:
            hits += 1
        else:
            misses.append((truth, guess, score))
    return hits, total, misses


class BackgroundModel:
    """La cámara está fija: lo que difiere de la bandeja vacía es el producto (y la mano).

    Trabaja a la mitad de resolución: alcanza para encontrar el producto y es ~4 veces más rápido.
    """

    def __init__(self, threshold: int = 30, learn_rate: float = 0.05):
        self._bg: np.ndarray | None = None
        self._threshold = threshold
        self._rate = learn_rate
        # (cuadro, cuadro preparado): se guarda el cuadro mismo, no su id, que Python reutiliza
        self._cache: tuple[np.ndarray, np.ndarray] | None = None

    def _prep(self, frame: np.ndarray) -> np.ndarray:
        if self._cache is not None and self._cache[0] is frame:
            return self._cache[1]
        small = cv2.resize(frame, None, fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA)
        prepped = cv2.GaussianBlur(cv2.cvtColor(small, cv2.COLOR_BGR2LAB), (5, 5), 0)
        prepped = prepped.astype(np.float32)
        self._cache = (frame, prepped)
        return prepped

    @property
    def ready(self) -> bool:
        return self._bg is not None

    def learn(self, frame: np.ndarray, foreground: np.ndarray | None = None) -> None:
        """Ajusta el fondo poco a poco (cambios de luz), nunca donde hay algo a la vista.

        Si se aprendiera también lo que está encima, un producto chico quedaría «dentro» del
        fondo y dejaría de verse (se iría sin cobrar).
        """
        current = self._prep(frame)
        if self._bg is None:
            self._bg = current
            return
        blended = cv2.addWeighted(self._bg, 1 - self._rate, current, self._rate, 0)
        if foreground is None:
            self._bg = blended
            return
        small = cv2.resize(foreground, (current.shape[1], current.shape[0]))
        keep = cv2.dilate((small > 0).astype(np.uint8), np.ones((3, 3), np.uint8))
        self._bg = np.where(keep[..., None] > 0, self._bg, blended)

    def foreground(self, frame: np.ndarray) -> np.ndarray:
        if self._bg is None:
            raise RuntimeError("Falta aprender la bandeja vacía")
        diff = np.abs(self._prep(frame) - self._bg).max(axis=2)
        mask = (diff > self._threshold).astype(np.uint8)
        kernel = np.ones((3, 3), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
        full = cv2.resize(mask, (frame.shape[1], frame.shape[0]), interpolation=cv2.INTER_NEAREST)
        return full.astype(np.float32)


Zone = tuple[float, float, float, float]  # x0, y0, x1, y1 en fracciones del cuadro


def parse_zone(text: str) -> Zone:
    """«0.2,0.1,0.8,0.9» → zona de escaneo. Falla con un mensaje claro si no tiene sentido."""
    try:
        x0, y0, x1, y1 = (float(v) for v in text.split(","))
    except ValueError:
        raise ValueError(f"Zona inválida «{text}»: se esperan 4 números x0,y0,x1,y1") from None
    if not (0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1):
        raise ValueError(f"Zona inválida «{text}»: deben cumplir 0 ≤ x0 < x1 ≤ 1 y 0 ≤ y0 < y1 ≤ 1")
    return x0, y0, x1, y1


def crop_zone(frame: np.ndarray, zone: Zone | None) -> np.ndarray:
    if zone is None:
        return frame
    rows, cols = frame.shape[:2]
    x0, y0, x1, y1 = zone
    return frame[int(y0 * rows) : int(y1 * rows), int(x0 * cols) : int(x1 * cols)]


def skin_mask(frame: np.ndarray) -> np.ndarray:
    """Piel (rango clásico en YCrCb): sirve para quitar la mano que sostiene el producto."""
    ycrcb = cv2.cvtColor(frame, cv2.COLOR_BGR2YCrCb)
    return cv2.inRange(ycrcb, (0, 133, 77), (255, 173, 127)) > 0


def remove_hands(frame: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Quita la piel solo de las manchas que tocan el borde: una mano siempre entra desde fuera.

    Un producto que descansa en medio de la zona no se toca aunque su empaque sea color piel,
    así nunca se «borra» algo que hay que cobrar.
    """
    binary = (mask > 0.5).astype(np.uint8)
    n, labels = cv2.connectedComponents(binary)
    if n <= 1:
        return mask
    edge = np.unique(np.concatenate([labels[0], labels[-1], labels[:, 0], labels[:, -1]]))
    touching = np.isin(labels, edge[edge > 0])
    cleaned = binary.copy()
    cleaned[touching & skin_mask(frame)] = 0
    # Lo que queda de la muñeca o la manga es una tira fina: la apertura la borra
    opened = cv2.morphologyEx(cleaned, cv2.MORPH_OPEN, np.ones((7, 7), np.uint8))
    return np.where(touching, opened, binary).astype(np.float32)


def foreground_regions(mask: np.ndarray, min_fraction: float) -> list[tuple[int, int, int, int]]:
    """Agrupa manchas cuyos recuadros se solapan: pueden ser partes del mismo empaque.

    No dilata ni une manchas separadas por distancia. Conserva el rechazo de dos objetos
    con recuadros separados y no inventa píxeles de producto entre fragmentos.
    """
    _, _, stats, _ = cv2.connectedComponentsWithStats((mask > 0.5).astype(np.uint8))
    boxes = [
        (int(x), int(y), int(x + w), int(y + h))
        for x, y, w, h, area in stats[1:]
        if area >= min_fraction * mask.size
    ]
    parents = list(range(len(boxes)))

    def root(i: int) -> int:
        while parents[i] != i:
            i = parents[i]
        return i

    for i, (x0, y0, x1, y1) in enumerate(boxes):
        for j in range(i):
            a0, b0, a1, b1 = boxes[j]
            if x0 < a1 and a0 < x1 and y0 < b1 and b0 < y1:
                parents[root(i)] = root(j)
    groups: dict[int, tuple[int, int, int, int]] = {}
    for i, (x0, y0, x1, y1) in enumerate(boxes):
        key = root(i)
        a0, b0, a1, b1 = groups.get(key, (x0, y0, x1, y1))
        groups[key] = min(x0, a0), min(y0, b0), max(x1, a1), max(y1, b1)
    return list(groups.values())


class SimilarityDetector:
    """Detector del quiosco: un producto a la vez frente a la cámara → [SKU], nada → []."""

    def __init__(
        self,
        embed: Embedder,
        gallery: Gallery,
        source: FrameSource,
        threshold: float = THRESHOLD,
        min_blob: float = 0.004,
        warmup_frames: int = 10,
        zone: Zone | None = None,
        hands: bool = True,
        segmenter: Callable[[np.ndarray], np.ndarray] | None = None,
        free_min_blob: float = 0.02,
    ):
        """`segmenter`: con él, modo «fondo libre» (ver el docstring del módulo); sin él, el
        fondo es la bandeja vacía que se aprende al arrancar. `free_min_blob`: fracción mínima
        del cuadro que debe ocupar el objeto en modo libre (el producto se acerca a la cámara)."""
        self._embed = embed
        self._gallery = gallery
        self._source = source
        self._threshold = threshold
        self._min_blob = min_blob
        self._warmup_frames = warmup_frames
        self._warmup = warmup_frames
        self._zone = zone  # solo se mira este recuadro: la zona de escaneo, no toda la bandeja
        self._hands = hands
        self._segmenter = segmenter
        self._free_min_blob = free_min_blob
        self._seen: str | None = None  # último resultado registrado en el log
        self._background = BackgroundModel()
        self._lock = threading.Lock()  # detect corre en otro hilo; recalibrate llega desde la API
        self.last: tuple[str, float] | None = None  # para depurar: mejor SKU y parecido

    @classmethod
    def from_files(
        cls,
        gallery: Path,
        source: FrameSource,
        embedder: Path = DEFAULT_EMBEDDER,
        segmenter: Path | None = None,
        **kwargs,
    ) -> "SimilarityDetector":
        """`segmenter`: ruta de silueta.onnx para el modo «fondo libre»."""
        loaded = Gallery.load(gallery)
        segment = Segmenter.from_model(segmenter) if segmenter is not None else None
        return cls(
            Embedder.from_model(embedder, loaded.size), loaded, source, segmenter=segment, **kwargs
        )

    @property
    def free_background(self) -> bool:
        """True si separa el producto del fondo con el segmentador (no necesita bandeja vacía)."""
        return self._segmenter is not None

    def _blobs(self, mask: np.ndarray) -> int:
        return len(foreground_regions(mask, self._min_blob))

    def recalibrate(self) -> None:
        """Olvida el fondo: los próximos cuadros (bandeja vacía) son el nuevo fondo."""
        with self._lock:
            self._background = BackgroundModel()
            self._warmup = self._warmup_frames
            self.last = None

    def detect(self) -> list[str]:
        with self._lock:
            return self._detect()

    def open(self) -> None:
        with self._lock:
            open_source = getattr(self._source, "open", None)
            if open_source is not None:
                open_source()

    def close(self) -> None:
        with self._lock:
            close_source = getattr(self._source, "close", None)
            if close_source is not None:
                close_source()

    def _report(self, result: list[str]) -> list[str]:
        """Registra en el log cada cambio de lo que se ve (con el mejor parecido), para ajustar
        KIOSK_THRESHOLD con pruebas reales sin inundar el log con cada cuadro."""
        label = result[0] if result else "nada"
        if label != self._seen:
            best = f"{self.last[0]} {self.last[1]:.2f}" if self.last else "—"
            log.info("Cámara: %s (mejor parecido: %s)", label, best)
            self._seen = label
        return result

    def _detect(self) -> list[str]:
        frame = crop_zone(self._source.read(), self._zone)
        if self._segmenter is not None:
            return self._report(self._detect_free(frame, self._segmenter))
        return self._report(self._detect_fixed(frame))

    def _detect_free(
        self, frame: np.ndarray, segment: Callable[[np.ndarray], np.ndarray]
    ) -> list[str]:
        """Fondo libre: el objeto más grande que separa «silueta», sin la mano que lo sostiene."""
        mask = (segment(frame) > 0.5).astype(np.float32)
        if self._hands:
            mask = remove_hands(frame, mask)
        regions = foreground_regions(mask, self._free_min_blob)
        if not regions:
            self.last = None
            return []
        x0, y0, x1, y1 = max(regions, key=lambda r: (r[2] - r[0]) * (r[3] - r[1]))
        product_mask = np.zeros_like(mask)
        product_mask[y0:y1, x0:x1] = mask[y0:y1, x0:x1]
        if (found := isolate(frame, product_mask, merge_components=True)) is None:
            self.last = None
            return []
        ranking = self._gallery.ranking(fingerprints(self._embed, *found)[0])
        self.last = ranking[0]
        sku, score = ranking[0]
        # Bajo el umbral no es «desconocido»: con fondo libre la cámara ve caras, manos y el cuarto
        return [sku] if score >= self._threshold else []

    def _detect_fixed(self, frame: np.ndarray) -> list[str]:
        if self._warmup > 0:  # los primeros cuadros, con la bandeja vacía, son el fondo
            self._warmup -= 1
            self._background.learn(frame)
            return []
        seen = self._background.foreground(frame)
        mask = remove_hands(frame, seen) if self._hands else seen
        regions = foreground_regions(mask, self._min_blob)
        if not regions:
            self._background.learn(frame, seen)  # tampoco aprende donde está la mano
            self.last = None
            return []
        # Dos cosas separadas a la vista: no se adivina cuál cobrar.
        if len(regions) > 1:
            self.last = None
            return [UNKNOWN]
        x0, y0, x1, y1 = regions[0]
        product_mask = np.zeros_like(mask)
        product_mask[y0:y1, x0:x1] = mask[y0:y1, x0:x1]
        if (found := isolate(frame, product_mask, merge_components=True)) is None:
            self.last = None
            return [UNKNOWN]
        ranking = self._gallery.ranking(fingerprints(self._embed, *found)[0])
        self.last = ranking[0]
        sku, score = ranking[0]
        return [sku] if score >= self._threshold else [UNKNOWN]


# Galería del recuadro guía («galeria --recuadro»). Medido con las 107 fotos del Drive, consulta =
# recuadro central del 60 % y cada foto fuera de la galería (ver docs/ml/reconocimiento.md):
# - galería solo con el producto recortado, color 0,5, mejor huella: 77,6 % de aciertos;
# - + recuadros centrales del 45/60/80 %, color medido en el centro, peso 0,8 y promedio de las
#   2 mejores huellas: 85,0 %;
# - y aceptando solo con parecido ≥ 1,2 y margen ≥ 0,05 sobre el segundo: acepta 82/107 y acierta
#   79 (96 %). El margen es lo que evita confundir empaques parecidos (Casino y Cancún).
BOX_CROPS = (0.45, 0.6, 0.8)
BOX_COLOR_WEIGHT = 0.8
BOX_TOP = 2
BOX_THRESHOLD = 1.2
BOX_MARGIN = 0.05
# Galerías hechas antes del recuadro (sin umbral guardado): los aciertos daban ~1,0–1,2.
LEGACY_BOX_THRESHOLD = 1.0
MAX_UPLOAD_BYTES = 2_000_000
MAX_UPLOAD_PIXELS = 4096 * 4096
# Marcadores JPEG «inicio de cuadro» (SOF): traen el alto y el ancho. C4, C8 y CC no lo son.
_JPEG_SOF = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}


def image_size(data: bytes) -> tuple[int, int] | None:
    """(ancho, alto) leídos de la cabecera PNG o JPEG, sin decodificar. None si no se reconoce."""
    if data[:8] == b"\x89PNG\r\n\x1a\n" and len(data) >= 24:
        return int.from_bytes(data[16:20]), int.from_bytes(data[20:24])
    if data[:2] != b"\xff\xd8":
        return None
    i = 2
    while i + 9 <= len(data):
        if data[i] != 0xFF:
            return None
        marker = data[i + 1]
        if marker in _JPEG_SOF:
            return int.from_bytes(data[i + 7 : i + 9]), int.from_bytes(data[i + 5 : i + 7])
        i += 2 + int.from_bytes(data[i + 2 : i + 4])
    return None


@dataclass(frozen=True)
class BoxMatch:
    """Resultado de reconocer un recuadro guía."""

    sku: str  # el más parecido (aunque no alcance el umbral)
    score: float
    margin: float  # ventaja sobre el segundo producto más parecido
    match: bool  # parecido y margen suficientes para tomarlo como ese producto


def _first(*values: float | None) -> float:
    """El primer valor que no sea None (el último siempre lo es)."""
    return next(v for v in values if v is not None)


class CropRecognizer:
    """Reconoce el «recuadro guía» que manda el navegador (y, a futuro, la app del celular).

    El cliente centra el producto en un recuadro de la pantalla y solo esa parte de la imagen
    llega aquí. No hay modelo de fondo ni segmentación (U²-Net tarda >1 s por cuadro en la laptop
    de desarrollo): el recorte va directo a la huella, ~100 ms. Un producto cuenta solo si se
    parece lo suficiente (`threshold`) y le saca ventaja al segundo (`margin`).
    """

    def __init__(
        self,
        embed: Embedder,
        gallery: Gallery,
        threshold: float | None = None,
        margin: float | None = None,
    ):
        self._embed = embed
        self._gallery = gallery
        # Lo que se pase manda; si no, lo medido para esta galería; si no, lo de antes.
        self.threshold = _first(threshold, gallery.threshold, LEGACY_BOX_THRESHOLD)
        self.margin = _first(margin, gallery.margin, 0.0)
        self._lock = threading.Lock()  # una sesión ONNX: una imagen a la vez

    @classmethod
    def from_files(
        cls,
        gallery: Path,
        embedder: Path = DEFAULT_EMBEDDER,
        threshold: float | None = None,
        margin: float | None = None,
    ) -> "CropRecognizer":
        """Carga la galería y el modelo DINOv2 del disco."""
        loaded = Gallery.load(gallery)
        return cls(Embedder.from_model(embedder, loaded.size), loaded, threshold, margin)

    def recognize(self, bgr: np.ndarray) -> BoxMatch:
        """Producto más parecido, su parecido y su ventaja sobre el segundo."""
        # Galería con recuadros: el color se mide en el centro, igual que en sus huellas.
        if self._gallery.views is not None:
            mask = center_mask(min(bgr.shape[:2]))
            side = mask.shape[0]
            top, left = (bgr.shape[0] - side) // 2, (bgr.shape[1] - side) // 2
            bgr = bgr[top : top + side, left : left + side]
        else:
            mask = np.ones(bgr.shape[:2], np.uint8)
        with self._lock:
            vector = fingerprints(self._embed, bgr, mask, color_weight=self._gallery.color_weight)[0]
        ranking = self._gallery.ranking(vector)
        sku, score = ranking[0]
        margin = score - ranking[1][1] if len(ranking) > 1 else score
        return BoxMatch(sku, score, margin, score >= self.threshold and margin >= self.margin)

    def recognize_bytes(self, data: bytes) -> BoxMatch | None:
        """Imagen JPEG/PNG tal como llega por HTTP. None si no es una imagen válida."""
        if not data or len(data) > MAX_UPLOAD_BYTES:
            return None
        size = image_size(data)
        if size is None or size[0] * size[1] > MAX_UPLOAD_PIXELS:
            return None  # se mira la cabecera antes de abrirla: 2 MB pueden ser miles de MP
        image = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
        if image is None or min(image.shape[:2]) < 32:
            return None
        return self.recognize(image)


class VerifiedYoloDetector:
    """Cobra solo cuando YOLO y la galería identifican el mismo empaque.

    YOLO propone una zona aunque haya personas detrás. La galería comprueba la
    apariencia del producto; un falso positivo sobre una persona se descarta.
    """

    def __init__(
        self,
        model: Path,
        gallery: Path,
        source: FrameSource,
        *,
        imgsz: int = 416,
        threshold: float = 0.90,
        embedder: Path = DEFAULT_EMBEDDER,
        segmenter: Path = DEFAULT_SEGMENTER,
    ):
        self._source = source
        self._yolo = YoloOnnxDetector.from_model(model, source, imgsz=imgsz, conf=0.35)
        self._gallery = Gallery.load(gallery)
        self._embed = Embedder.from_model(embedder, self._gallery.size)
        self._segment = Segmenter.from_model(segmenter)
        self._threshold = threshold
        self._imgsz = imgsz
        self._votes: deque[str | None] = deque(maxlen=12)
        self._held_sku: str | None = None
        self._last_seen = 0.0
        self.last: tuple[str, float] | None = None

    def _crop(self, frame: np.ndarray, detection: Detection) -> np.ndarray | None:
        rows, cols = frame.shape[:2]
        scale = min(self._imgsz / rows, self._imgsz / cols)
        top = (self._imgsz - round(rows * scale)) // 2
        left = (self._imgsz - round(cols * scale)) // 2
        x, y, width, height = detection.box
        x0 = max(0, int((x - left) / scale))
        y0 = max(0, int((y - top) / scale))
        x1 = min(cols, int((x + width - left) / scale))
        y1 = min(rows, int((y + height - top) / scale))
        if x1 <= x0 or y1 <= y0:
            return None
        # Un recuadro casi de pantalla completa incluye caras y fondo. El empaque
        # se presenta en el centro de la lente; conservar esa zona evita mezclarlo.
        if (x1 - x0) * (y1 - y0) > 0.5 * rows * cols:
            cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
            half_w, half_h = int(0.325 * (x1 - x0)), int(0.275 * (y1 - y0))
            x0, x1 = max(0, cx - half_w), min(cols, cx + half_w)
            y0, y1 = max(0, cy - half_h), min(rows, cy + half_h)
        return frame[y0:y1, x0:x1]

    def detect(self) -> list[str]:
        frame = self._source.read()
        self.last = None
        proposals = self._yolo.detections(frame)
        now = time.monotonic()
        if self._held_sku is not None:
            if any(self._yolo.class_names[d.class_id] == self._held_sku for d in proposals):
                self._last_seen = now
                return [self._held_sku]
            # Dos cuadros perdidos no representan una segunda unidad. Para otro
            # SKU se permite cambiar en cuanto pase dos verificaciones; para el
            # mismo SKU se exige una salida real y sostenida del encuadre.
            if now - self._last_seen >= 3.0:
                self._held_sku = None
                self._votes.clear()
        vote = None
        for detection in proposals:
            sku = self._yolo.class_names[detection.class_id]
            crop = self._crop(frame, detection)
            if crop is None:
                continue
            # Primero se comprueba el recuadro de YOLO directamente (~150 ms).
            # La segmentación completa queda para resultados débiles o confusos.
            fast = isolate(crop, np.ones(crop.shape[:2], np.float32))
            if fast is not None:
                ranking = self._gallery.ranking(fingerprints(self._embed, *fast)[0])
                gallery_score = next((score for label, score in ranking if label == sku), -1.0)
                competitor = max((score for label, score in ranking if label != sku), default=-1.0)
                if gallery_score >= 0.92 and gallery_score - competitor >= 0.04:
                    self.last = (sku, gallery_score)
                    vote = sku
                    break
            if (found := isolate(crop, self._segment(crop))) is None:
                continue
            ranking = self._gallery.ranking(fingerprints(self._embed, *found)[0])
            if ranking:
                self.last = ranking[0]
                gallery_score = next((score for label, score in ranking if label == sku), -1.0)
                if gallery_score >= self._threshold and ranking[0][1] - gallery_score <= 0.03:
                    vote = sku
                    break
        self._votes.append(vote)
        counts = Counter(label for label in self._votes if label is not None)
        for sku, hits in counts.most_common():
            if hits >= 2 and sku != self._held_sku:
                self._held_sku = sku
                self._last_seen = now
                self._votes.clear()
                return [sku]
        if self._held_sku is not None:
            return [self._held_sku]
        return []

    def open(self) -> None:
        self._yolo.open()

    def close(self) -> None:
        self._yolo.close()

    def recalibrate(self) -> None:
        """No requiere aprender el fondo; conserva la acción de la interfaz."""


def benchmark(gallery: Path, embedder: Path, raw: Path, frames: int) -> int:
    """Simula la bandeja (640×480) con una foto real encima y mide cada cuadro completo."""
    from kiosk.vision import ImageFolderSource

    photo = next((p for p in sorted(raw.rglob("*")) if p.suffix.lower() in IMAGE_EXT), None)
    if photo is None or (image := imread(photo)) is None:
        print(f"No hay fotos en {raw}")
        return 1
    empty = np.full((480, 640, 3), 200, np.uint8)
    with_product = empty.copy()
    with_product[140:340, 245:395] = cv2.resize(image, (150, 200))
    detector = SimilarityDetector.from_files(
        gallery, ImageFolderSource([empty] * 10 + [with_product] * (frames + 10)), embedder
    )
    for _ in range(20):
        detector.detect()
    times = []
    for _ in range(frames):
        start = time.perf_counter()
        detector.detect()
        times.append((time.perf_counter() - start) * 1000)
    p50, p95 = np.percentile(times, 50), np.percentile(times, 95)
    verdict = "cumple" if p95 <= 150 else "NO cumple"
    print(
        f"{frames} cuadros: p50 {p50:.0f} ms · p95 {p95:.0f} ms → RNF-01 (p95 ≤ 150 ms) {verdict}"
    )
    print("Mide con la laptop de la demo enchufada y sin otros programas abiertos.")
    return 0


def capture(sku: str, raw: Path, camera: int, count: int, every_s: float) -> int:
    """Fotos en el mismo lugar, luz y cámara que la demo: es lo que más mejora el acierto."""
    folder = raw / sku
    folder.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    source = CameraSource(camera)
    try:
        print(f"Mueve y gira {sku} bajo la cámara; se guardan {count} fotos…")
        for i in range(1, count + 1):
            time.sleep(every_s)
            path = folder / f"CAM_{stamp}_{i:03d}.jpg"
            ok, data = cv2.imencode(".jpg", source.read())
            if ok:
                data.tofile(path)
            print(f"  {path.name}")
    finally:
        source.close()
    print("Listo. Vuelve a generar la galería: python -m kiosk.recognizer galeria")
    return 0


def draw_zone(frame: np.ndarray, zone: Zone) -> np.ndarray:
    out = frame.copy()
    rows, cols = frame.shape[:2]
    x0, y0, x1, y1 = zone
    p0, p1 = (int(x0 * cols), int(y0 * rows)), (int(x1 * cols) - 1, int(y1 * rows) - 1)
    cv2.rectangle(out, p0, p1, (0, 220, 255), 3)
    return out


def show_zone(zone: Zone, camera: int, out: Path) -> int:
    """Foto de la cámara con el recuadro: sirve para elegir KIOSK_ZONE sin adivinar."""
    source = CameraSource(camera)
    try:
        frame = source.read()
    finally:
        source.close()
    ok, data = cv2.imencode(".jpg", draw_zone(frame, zone))
    if ok:
        data.tofile(out)
    print(f"Zona dibujada en {out}. Si está bien: KIOSK_ZONE={','.join(f'{v:g}' for v in zone)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Reconocimiento por parecido (galería de fotos).")
    sub = parser.add_subparsers(dest="cmd", required=True)
    build = sub.add_parser("galeria", help="genera la galería desde ml/data/raw")
    build.add_argument("--raw", type=Path, default=REPO / "ml" / "data" / "raw")
    build.add_argument("--catalogo", type=Path, default=REPO / "catalog" / "products.csv")
    build.add_argument("--segmenter", type=Path, default=DEFAULT_SEGMENTER)
    build.add_argument("--tamano", type=int, default=EMBED_SIZE, help="lado para DINOv2 (×14)")
    build.add_argument(
        "--recuadro",
        action="store_true",
        help="galería para la cámara del navegador (recuadro guía): galeria-recuadro.npz",
    )
    sub.add_parser("evaluar", help="aciertos dejando cada foto fuera")
    live = sub.add_parser("camara", help="prueba en vivo con la webcam")
    live.add_argument("--camera", type=int, default=0)
    live.add_argument("--frames", type=int, default=100)
    live.add_argument("--zona", type=parse_zone, default=None, help="x0,y0,x1,y1 (KIOSK_ZONE)")
    live.add_argument(
        "--fondo", choices=["fijo", "libre"], default="fijo", help="KIOSK_FONDO (ver el inicio)"
    )
    live.add_argument("--segmenter", type=Path, default=DEFAULT_SEGMENTER)
    frame_zone = sub.add_parser("zona", help="guarda una foto con la zona de escaneo dibujada")
    frame_zone.add_argument(
        "zona", type=parse_zone, help="x0,y0,x1,y1 en fracciones, p. ej. 0.25,0.1,0.75,0.9"
    )
    frame_zone.add_argument("--camera", type=int, default=0)
    frame_zone.add_argument("--salida", type=Path, default=Path("zona.jpg"))
    bench = sub.add_parser("medir", help="ms por cuadro con la galería (RNF-01: ≤ 150 ms)")
    bench.add_argument("--raw", type=Path, default=REPO / "ml" / "data" / "raw")
    bench.add_argument("--cuadros", type=int, default=100)
    shoot = sub.add_parser("capturar", help="guarda fotos de un producto con la cámara del quiosco")
    shoot.add_argument("sku")
    shoot.add_argument("--camera", type=int, default=0)
    shoot.add_argument("--fotos", type=int, default=20)
    shoot.add_argument("--cada", type=float, default=0.7, help="segundos entre fotos")
    shoot.add_argument("--raw", type=Path, default=REPO / "ml" / "data" / "raw")
    parser.add_argument("--galeria", type=Path, default=DEFAULT_GALLERY)
    parser.add_argument("--embedder", type=Path, default=DEFAULT_EMBEDDER)
    args = parser.parse_args(argv)

    if args.cmd == "galeria":
        from kiosk.catalog import Catalog

        skus = {p.sku for p in Catalog.from_csv(args.catalogo).all()}
        missing = sorted(skus - {p.name for p in args.raw.iterdir() if p.is_dir()})
        if args.recuadro and args.galeria == DEFAULT_GALLERY:
            args.galeria = DEFAULT_BOX_GALLERY
        gallery = build_gallery(
            args.raw,
            Embedder.from_model(args.embedder, args.tamano),
            Segmenter.from_model(args.segmenter),
            skus,
            crops=BOX_CROPS if args.recuadro else (),
            color_weight=BOX_COLOR_WEIGHT if args.recuadro else COLOR_WEIGHT,
            top=BOX_TOP if args.recuadro else 1,
        )
        if args.recuadro:
            gallery.threshold, gallery.margin = BOX_THRESHOLD, BOX_MARGIN
        gallery.save(args.galeria)
        photos, products = len(np.unique(gallery.photos)), len(np.unique(gallery.labels))
        print(f"Galería: {photos} fotos de {products} productos → {args.galeria}")
        if missing:
            print(f"Sin fotos (no se podrán reconocer): {', '.join(missing)}")
        return 0
    if args.cmd == "evaluar":
        loaded = Gallery.load(args.galeria)
        # Galería del recuadro: se evalúa como la usa el navegador (recuadro central del 60 %)
        query = "c60" if loaded.views is not None and "c60" in loaded.views else None
        hits, total, misses = leave_one_out(loaded, query)
        print(f"Aciertos dejando cada foto fuera: {hits}/{total} = {hits / total:.0%}")
        for truth, guess, score in misses:
            print(f"  {truth} → {guess} ({score:.2f})")
        return 0
    if args.cmd == "medir":
        return benchmark(args.galeria, args.embedder, args.raw, args.cuadros)
    if args.cmd == "capturar":
        return capture(args.sku, args.raw, args.camera, args.fotos, args.cada)
    if args.cmd == "zona":
        return show_zone(args.zona, args.camera, args.salida)
    source = CameraSource(args.camera)
    try:
        detector = SimilarityDetector.from_files(
            args.galeria,
            source,
            args.embedder,
            segmenter=args.segmenter if args.fondo == "libre" else None,
            zone=args.zona,
        )
        for _ in range(args.frames):
            start = time.perf_counter()
            seen = detector.detect()
            best = f"{detector.last[0]} {detector.last[1]:.2f}" if detector.last else "—"
            print(f"{(time.perf_counter() - start) * 1000:6.1f} ms  {seen}  (mejor: {best})")
    finally:
        source.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
