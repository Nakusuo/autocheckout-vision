# Guía de etiquetado (Label Studio)

Etiquetar significa dibujar un recuadro alrededor de cada producto en cada foto y decir cuál es. El modelo aprende de esos recuadros, así que **la calidad del etiquetado es la calidad del reconocedor**.

## 1. Preparar (una vez)

```bash
# Un entorno aparte para Label Studio
python -m venv ~/label-studio-env && source ~/label-studio-env/Scripts/activate   # Linux/Mac: bin/activate
pip install label-studio
label-studio start        # abre http://localhost:8080 y pide crear un usuario local
```

## 2. Revisar el dataset antes de etiquetar

Descarga la carpeta del Drive **AutoCaja-dataset** dentro de `ml/data/raw/` y ejecuta desde `ml/`:

```bash
python -m mltools.dataset_check          # corrige lo que marque ❌ antes de seguir
python -m mltools.frames ml/data/raw/videos/JP_cocacola.mp4 --out ml/data/raw/COCACOLA-500
```

## 3. Crear el proyecto

1. En Label Studio: **Create Project** → nombre `AutoCaja`.
2. **Labeling Setup → Custom template → Code**: pega lo que imprime `python -m mltools.labelstudio`. Sale una etiqueta por producto del catálogo.
3. **Data Import**: arrastra las fotos de las carpetas, de a una o dos carpetas por vez.

## 4. Reglas para dibujar

- ✅ **Un recuadro por producto**, ajustado a sus bordes, sin dejar mucho espacio.
- ✅ Si hay 3 productos, van **3 recuadros**, cada uno con su etiqueta.
- ✅ Producto cortado por el borde de la foto: se etiqueta si se ve **más de la mitad**.
- ✅ Productos que se tapan: cada uno lleva su propio recuadro, aunque se superpongan.
- ❌ No etiquetes reflejos, sombras ni productos que no están en el catálogo.
- ❌ Si una foto está borrosa o sale una persona: **Skip** y avisa para borrarla.

## 5. Exportar

Cuando todo esté etiquetado: **Export → YOLO** y descomprime el resultado en `ml/data/labeled/`. Esa carpeta, igual que `ml/data/raw/`, está fuera de git.

## Reparto sugerido

Cada persona etiqueta las fotos que **no** tomó. Así un segundo par de ojos revisa cada foto.
