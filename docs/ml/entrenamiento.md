# Entrenamiento del reconocedor

Requisito previo: fotos etiquetadas y exportadas desde Label Studio (ver [etiquetado.md](etiquetado.md)).

## 1. Exportación → dataset

Descomprime la exportación **YOLO** de Label Studio en `ml/data/labeled/`. Tiene que quedar así:

```
ml/data/labeled/
  classes.txt
  images/   (fotos)
  labels/   (un .txt por foto)
```

Desde `ml/` (venv del proyecto):

```bash
python -m mltools.split        # valida y reparte 70/20/10 en data/dataset/ + data.yaml
```

Si marca ❌, corrige en Label Studio y vuelve a exportar.

## 2. Entrenar (CPU)

El entrenamiento usa Ultralytics (AGPL-3.0), que pesa más de 1 GB. Va en un entorno aparte, con una ruta corta por el límite de rutas largas de Windows:

```bash
python -m venv ~/.venvs/yolo && source ~/.venvs/yolo/Scripts/activate
pip install --index-url https://download.pytorch.org/whl/cpu torch torchvision
pip install -e "ml[train]"          # desde la raíz del repo

cd ml
python -m mltools.train --epochs 100
```

Al terminar deja `data/models/autocaja-416.onnx` y `autocaja-416.json`, e imprime:

- `mAP50 en test … CUMPLE / NO CUMPLE` (meta ≥ 0,90).
- El comando para medir la latencia (RNF-01).

En CPU, con unas 800 fotos, puede tardar **varias horas**. Para probar el flujo rápido usa `--epochs 5`.

### Alternativa con GPU gratuita

Google Colab: sube `data/dataset/` y ejecuta los mismos comandos. Ten en cuenta que las fotos quedan en servidores de Google.

## 3. Si no cumple la meta

1. Revisa en `data/models/runs/autocaja/` las matrices de confusión: ¿qué productos se confunden?
2. Más fotos de esos productos, sobre todo en `mezclas`.
3. Probar con `--imgsz 480` (y volver a medir la latencia).

## 4. Usarlo en el quiosco

```bash
export KIOSK_MODE=camera
export KIOSK_MODEL=../ml/data/models/autocaja-416.onnx
python -m kiosk
```
