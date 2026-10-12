# Reconocimiento por parecido (sin entrenar)

**Decisión (2026-10-12):** el Drive tiene **56 fotos de 11 productos** (4 a 8 por producto), lejos de las ~100 por producto que pide un YOLOv8 entrenado. Como el cliente pasa los productos **de a uno** frente a la cámara, no hace falta un detector multiproducto: basta con reconocer el único producto a la vista. Se usa un modelo **preentrenado** que no se entrena con nuestros datos. El YOLOv8 del SRS queda como camino futuro (`KIOSK_MODEL`) cuando haya dataset.

## Cómo funciona (`kiosk-api/src/kiosk/recognizer.py`)

1. **Recorte del producto, con el fondo en gris.**
   - En las fotos de referencia lo hace un modelo que quita el fondo (U²-Net «silueta»).
   - En el quiosco, la cámara está fija: los primeros cuadros, con la bandeja vacía, son el fondo, y lo que difiere de él es el producto.
2. **Huella del recorte.**
   - DINOv2-small aporta la forma y el estampado del empaque.
   - Un histograma de color (tono × saturación) aporta los colores. El color pesa 0,5.
3. **Comparación con la galería**, que guarda cada foto de referencia en 4 rotaciones.
   - Gana el producto más parecido.
   - Si el parecido no llega al umbral (0,95, configurable con `KIOSK_THRESHOLD`), el resultado es `DESCONOCIDO` y el quiosco muestra «Hay un producto que no reconocemos».

**Agregar un producto** es agregar sus fotos y volver a generar la galería. No hay que entrenar.

## Resultados con el dataset actual

Cada foto se reconoce comparándola con las demás:

| Variante | Aciertos |
|---|---|
| Imagen completa (DINOv2) | 66 % (compara la mesa, no el producto) |
| Puntos clave SIFT | 59 % (coinciden la mesa y las piedras del fondo) |
| Recorte + DINOv2 | 70 % |
| **Recorte + DINOv2 + color (elegida)** | **91 %** (51/56); **98 % sin los reversos** (46/47) |

Casi todos los fallos son fotos del **reverso** (código de barras, tabla nutricional), que no tienen otra foto del reverso con qué compararse. Velocidad: unos 50 ms por cuadro en CPU.

## Pasos

Requisitos:
- en `kiosk-api`: `pip install -e ".[dev,vision]"`;
- en `ml`: `pip install -e ".[dev,heic]"`.

```bash
# 1. Modelos preentrenados (una vez; quedan en ml/data/models, fuera de git)
curl -L -o ml/data/models/dinov2-small.onnx https://huggingface.co/onnx-community/dinov2-small/resolve/main/onnx/model.onnx
curl -L -o ml/data/models/silueta.onnx https://github.com/danielgatis/rembg/releases/download/v0.0.0/silueta.onnx

# 2. Fotos del Drive → ml/data/raw/<SKU>/ (convierte .heic; «KRpiña-3,03L» → «KRPINA-3.03L»)
cd ml && python -m mltools.importar RUTA/AutoCaja-dataset

# 3. Galería y evaluación (desde kiosk-api)
python -m kiosk.recognizer galeria      # solo productos de catalog/products.csv
python -m kiosk.recognizer evaluar

# 4. Probar en vivo: imprime el producto y el parecido de cada cuadro
#    (empieza con la bandeja vacía: los primeros cuadros son el fondo)
python -m kiosk.recognizer camara --camera 0

# 5. Quiosco con cámara
KIOSK_MODE=camera KIOSK_GALLERY=../ml/data/models/galeria.npz python -m kiosk
```

## Lo que más mejora el acierto

**Fotos con la cámara y la bandeja de la demo.** Las fotos del Drive se tomaron con celulares, sobre una mesa de madera. La webcam de la demo ve otra luz, otro ángulo y otro fondo.

```bash
python -m kiosk.recognizer capturar CANCUN-33 --camera 0   # 20 fotos; mueve y gira el producto
python -m kiosk.recognizer galeria
```

Con 10 a 20 fotos por producto tomadas así, el reconocimiento en vivo se parece mucho más a la prueba. Después de capturar:
- revisa con `camara` qué parecido dan los aciertos;
- ajusta `KIOSK_THRESHOLD` justo por debajo de ese valor.

## Límites conocidos

- **Un producto a la vez.** Si hay dos a la vista, se recorta la mancha más grande. Esto calza con el flujo actual (W2 «En vivo»).
- **La mano cuenta como parte del producto** si lo sostiene. Conviene dejar el producto sobre la zona de escaneo y retirar la mano.
- **Fondo.** Si cambia mucho la luz con algo a la vista, el fondo se reajusta solo cuando no hay nada. Si la cámara se mueve, reinicia el quiosco con la bandeja vacía.
- **Productos parecidos entre sí** (galletas en empaque rojo o blanco): necesitan más fotos del frente.
