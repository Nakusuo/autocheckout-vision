# Benchmark de latencia (RNF-01)

Medido el 2026-10-03 con `python -m mltools.bench` (50 corridas, preprocesado + inferencia, ONNX Runtime en CPU) usando **YOLOv8n preentrenado** (COCO), en la laptop de desarrollo (8 hilos, sin GPU).

| Tamaño de entrada | Media | p50 | p95 | RNF-01 (p95 ≤ 150 ms) |
|---|---|---|---|---|
| 640 px | 180–243 ms | 180–232 ms | 199–305 ms | ❌ No cumple |
| 480 px | 93 ms | 93 ms | 128 ms | ✅ Cumple (poco margen) |
| 416 px | 77 ms | 65 ms | 126 ms | ✅ Cumple |
| 320 px | 39 ms | 34 ms | 62 ms | ✅ Cumple con holgura |

## Decisión

- **Se entrena y exporta a 416 px.** Cumple con margen, y la cámara cenital ve los productos grandes en la bandeja, así que perder resolución afecta poco.
- Si en la evaluación del M1 la precisión (mAP50 ≥ 0.90) no se alcanza a 416, probar 480 y volver a medir.
- 640 px queda descartado en esta laptop.
- Repetir esta medición en el equipo real del quiosco antes de la demo (M5).

Comando para repetirla (desde `ml/`):

```bash
python -m mltools.bench --model data/models/yolov8n-416.onnx --imgsz 416
```

## Reconocimiento por parecido

El modo cámara usa la galería de fotos (ver [`reconocimiento.md`](reconocimiento.md)), no YOLOv8. Se mide desde `kiosk-api` con:

```bash
python -m kiosk.recognizer medir
```

En la laptop de desarrollo: huella DINOv2 ~105 ms (p50) a 140 px (~250 ms a 224 px); cuadro completo ~110–150 ms según la carga. **Pendiente: medir en la laptop de la demo**, enchufada y con los demás programas cerrados, y anotar aquí el p95.
