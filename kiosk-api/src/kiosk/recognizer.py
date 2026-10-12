"""Reconocimiento por parecido (requiere el extra `vision`).

Con ~5 fotos por producto no alcanza para entrenar un detector, así que no se entrena nada:
1. Se recorta el producto y se pinta el fondo de gris (en la galería, con un modelo que quita
   el fondo; en el quiosco, comparando con la bandeja vacía, porque la cámara está fija).
2. Su «huella» une la descripción de DINOv2 (forma y estampado) con un histograma de color.
3. Se compara con la huella de cada foto de referencia (en 4 rotaciones: la cámara mira desde
   arriba y el producto puede estar girado). Si nada se parece lo suficiente: DESCONOCIDO.

Agregar un producto es agregar sus fotos y volver a generar la galería.

Uso (las opciones --galeria y --embedder van antes del comando):
    python -m kiosk.recognizer galeria
    python -m kiosk.recognizer evaluar
    python -m kiosk.recognizer camara --camera 0
    python -m kiosk.recognizer capturar CANCUN-33 --camera 0   # fotos con la cámara de la demo
    python -m kiosk.recognizer medir                           # ms por cuadro (RNF-01: ≤ 150)
"""

import argparse
import threading
import time
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from kiosk.vision import CameraSource, FrameSource

REPO = Path(__file__).resolve().parents[3]
MODELS = REPO / "ml" / "data" / "models"
DEFAULT_EMBEDDER = MODELS / "dinov2-small.onnx"
DEFAULT_SEGMENTER = MODELS / "silueta.onnx"
DEFAULT_GALLERY = MODELS / "galeria.npz"

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


def isolate(bgr: np.ndarray, mask: np.ndarray) -> tuple[np.ndarray, np.ndarray] | None:
    """Recorta la mancha más grande de la máscara, con el fondo en gris, en un cuadrado."""
    binary = (mask > 0.5).astype(np.uint8)
    n, _, stats, _ = cv2.connectedComponentsWithStats(binary)
    if n <= 1:
        return None
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

        return cls(ort.InferenceSession(str(path), providers=["CPUExecutionProvider"]))

    def __call__(self, bgr: np.ndarray) -> np.ndarray:
        out = self._session.run(None, {self._input: _normalize(bgr, 320)[None]})[0][0, 0]
        out = (out - out.min()) / (out.max() - out.min() + 1e-6)
        return cv2.resize(out, (bgr.shape[1], bgr.shape[0]))


def fingerprints(
    embed: Embedder, crop: np.ndarray, mask: np.ndarray, rotations: int = 1
) -> np.ndarray:
    """Huella = [DINOv2, √peso·color]: el producto punto suma ambos parecidos."""
    views = [crop] + [cv2.rotate(crop, r) for r in (0, 1, 2)][: rotations - 1]
    shape = embed(views)
    color = np.sqrt(COLOR_WEIGHT) * color_hist(crop, mask)
    return np.hstack([shape, np.tile(color, (len(views), 1))]).astype(np.float32)


@dataclass
class Gallery:
    vectors: np.ndarray  # (n, d)
    labels: np.ndarray  # (n,) SKU de cada huella
    photos: np.ndarray  # (n,) foto de origen (las 4 rotaciones comparten número)
    size: int = EMBED_SIZE  # el quiosco debe describir los cuadros con el mismo tamaño

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(
            path, vectors=self.vectors, labels=self.labels, photos=self.photos, size=self.size
        )

    @classmethod
    def load(cls, path: Path) -> "Gallery":
        with np.load(path, allow_pickle=False) as data:
            size = int(data["size"]) if "size" in data.files else 224
            return cls(data["vectors"], data["labels"], data["photos"], size)

    def ranking(self, vector: np.ndarray, skip_photo: int | None = None) -> list[tuple[str, float]]:
        """Mejor parecido por SKU, de mayor a menor."""
        scores = self.vectors @ vector
        best: dict[str, float] = {}
        for label, photo, score in zip(self.labels, self.photos, scores, strict=True):
            if photo == skip_photo:
                continue
            best[str(label)] = max(best.get(str(label), -9.0), float(score))
        return sorted(best.items(), key=lambda kv: -kv[1])


def build_gallery(
    raw: Path, embed: Embedder, segment: Segmenter, skus: set[str] | None = None
) -> Gallery:
    vectors, labels, photos = [], [], []
    photo = 0
    folders = sorted(p for p in raw.iterdir() if p.is_dir() and (skus is None or p.name in skus))
    for folder in folders:
        for path in sorted(p for p in folder.iterdir() if p.suffix.lower() in IMAGE_EXT):
            image = imread(path)
            if image is None or (found := isolate(image, segment(image))) is None:
                print(f"  sin producto visible, se omite: {folder.name}/{path.name}")
                continue
            fp = fingerprints(embed, *found, rotations=4)
            vectors.append(fp)
            labels += [folder.name] * len(fp)
            photos += [photo] * len(fp)
            photo += 1
    if not vectors:
        raise ValueError(f"No hay fotos en {raw}")
    size = getattr(embed, "size", EMBED_SIZE)
    return Gallery(np.vstack(vectors), np.array(labels), np.array(photos), size)


def leave_one_out(gallery: Gallery) -> tuple[int, int, list[tuple[str, str, float]]]:
    """Reconoce cada foto (sin rotar) con las demás. Devuelve aciertos, total y fallos."""
    hits, total, misses = 0, 0, []
    for photo in np.unique(gallery.photos):
        i = int(np.flatnonzero(gallery.photos == photo)[0])
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
    ):
        self._embed = embed
        self._gallery = gallery
        self._source = source
        self._threshold = threshold
        self._min_blob = min_blob
        self._warmup_frames = warmup_frames
        self._warmup = warmup_frames
        self._background = BackgroundModel()
        self._lock = threading.Lock()  # detect corre en otro hilo; recalibrate llega desde la API
        self.last: tuple[str, float] | None = None  # para depurar: mejor SKU y parecido

    @classmethod
    def from_files(
        cls, gallery: Path, source: FrameSource, embedder: Path = DEFAULT_EMBEDDER, **kwargs
    ) -> "SimilarityDetector":
        loaded = Gallery.load(gallery)
        return cls(Embedder.from_model(embedder, loaded.size), loaded, source, **kwargs)

    def _blobs(self, mask: np.ndarray) -> int:
        """Manchas que no son ruido: cualquier producto, aunque sea chico, cuenta."""
        n, _, stats, _ = cv2.connectedComponentsWithStats((mask > 0.5).astype(np.uint8))
        min_px = self._min_blob * mask.size
        return int((stats[1:, cv2.CC_STAT_AREA] >= min_px).sum()) if n > 1 else 0

    def recalibrate(self) -> None:
        """Olvida el fondo: los próximos cuadros (bandeja vacía) son el nuevo fondo."""
        with self._lock:
            self._background = BackgroundModel()
            self._warmup = self._warmup_frames
            self.last = None

    def detect(self) -> list[str]:
        with self._lock:
            return self._detect()

    def _detect(self) -> list[str]:
        frame = self._source.read()
        if self._warmup > 0:  # los primeros cuadros, con la bandeja vacía, son el fondo
            self._warmup -= 1
            self._background.learn(frame)
            return []
        mask = self._background.foreground(frame)
        blobs = self._blobs(mask)
        if blobs == 0:
            self._background.learn(frame, mask)
            self.last = None
            return []
        # Dos cosas separadas a la vista: no se adivina cuál cobrar; el quiosco avisa y bloquea
        # PAGAR hasta que quede una sola.
        if blobs > 1 or (found := isolate(frame, mask)) is None:
            self.last = None
            return [UNKNOWN]
        ranking = self._gallery.ranking(fingerprints(self._embed, *found)[0])
        self.last = ranking[0]
        sku, score = ranking[0]
        return [sku] if score >= self._threshold else [UNKNOWN]


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
    print(f"{frames} cuadros: p50 {p50:.0f} ms · p95 {p95:.0f} ms → RNF-01 (p95 ≤ 150 ms) {verdict}")
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Reconocimiento por parecido (galería de fotos).")
    sub = parser.add_subparsers(dest="cmd", required=True)
    build = sub.add_parser("galeria", help="genera la galería desde ml/data/raw")
    build.add_argument("--raw", type=Path, default=REPO / "ml" / "data" / "raw")
    build.add_argument("--catalogo", type=Path, default=REPO / "catalog" / "products.csv")
    build.add_argument("--segmenter", type=Path, default=DEFAULT_SEGMENTER)
    build.add_argument("--tamano", type=int, default=EMBED_SIZE, help="lado para DINOv2 (×14)")
    sub.add_parser("evaluar", help="aciertos dejando cada foto fuera")
    live = sub.add_parser("camara", help="prueba en vivo con la webcam")
    live.add_argument("--camera", type=int, default=0)
    live.add_argument("--frames", type=int, default=100)
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
        gallery = build_gallery(
            args.raw,
            Embedder.from_model(args.embedder, args.tamano),
            Segmenter.from_model(args.segmenter),
            skus,
        )
        gallery.save(args.galeria)
        photos, products = len(np.unique(gallery.photos)), len(np.unique(gallery.labels))
        print(f"Galería: {photos} fotos de {products} productos → {args.galeria}")
        if missing:
            print(f"Sin fotos (no se podrán reconocer): {', '.join(missing)}")
        return 0
    if args.cmd == "evaluar":
        hits, total, misses = leave_one_out(Gallery.load(args.galeria))
        print(f"Aciertos dejando cada foto fuera: {hits}/{total} = {hits / total:.0%}")
        for truth, guess, score in misses:
            print(f"  {truth} → {guess} ({score:.2f})")
        return 0
    if args.cmd == "medir":
        return benchmark(args.galeria, args.embedder, args.raw, args.cuadros)
    if args.cmd == "capturar":
        return capture(args.sku, args.raw, args.camera, args.fotos, args.cada)
    source = CameraSource(args.camera)
    try:
        detector = SimilarityDetector.from_files(args.galeria, source, args.embedder)
        for _ in range(args.frames):
            start = time.perf_counter()
            skus = detector.detect()
            best = f"{detector.last[0]} {detector.last[1]:.2f}" if detector.last else "—"
            print(f"{(time.perf_counter() - start) * 1000:6.1f} ms  {skus}  (mejor: {best})")
    finally:
        source.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
