# AutoCaja en Hugging Face Spaces (Docker, plan gratis): API + reconocimiento + interfaz en un solo
# contenedor y una sola dirección https. Build desde la raíz del repo:
#   docker build -f deploy/hf/Dockerfile -t autocaja-hf .
# El CD (.github/workflows/cd.yml) arma la carpeta del Space con este archivo como Dockerfile.

# 1) Interfaz: React compilado a archivos estáticos.
FROM node:22-alpine AS ui
WORKDIR /ui
COPY kiosk-ui/package.json kiosk-ui/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY kiosk-ui/ ./
RUN npm run build

# 2) API con el extra de visión; la misma API sirve la interfaz (KIOSK_UI_DIR), sin nginx.
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Spaces corre el contenedor con el usuario 1000.
RUN useradd --uid 1000 --create-home user \
    && mkdir -p /app/ml/data/models /datos \
    && chown -R user:user /app /datos

# Misma estructura que el repo: el código busca catalog/ y ml/data/models/ desde la raíz.
WORKDIR /app
COPY catalog/products.csv catalog/products.csv
COPY kiosk-api/pyproject.toml kiosk-api/pyproject.toml
COPY kiosk-api/src kiosk-api/src
RUN pip install --timeout 120 --retries 5 -e "./kiosk-api[vision]" "huggingface_hub>=0.24"
COPY --from=ui /ui/dist /app/ui
COPY deploy/hf/arrancar.py /app/arrancar.py

USER user
# Puerto de Spaces (app_port en README.md). Los modelos y el QR los baja arrancar.py.
ENV KIOSK_HOST=0.0.0.0 \
    KIOSK_PORT=7860 \
    KIOSK_DATA_DIR=/datos \
    KIOSK_MODE=web \
    KIOSK_PAYMENT=yape-qr \
    KIOSK_UI_DIR=/app/ui \
    KIOSK_GALLERY=/app/ml/data/models/galeria-recuadro.npz \
    KIOSK_YAPE_QR=/app/ml/data/models/yape-qr.png
EXPOSE 7860
CMD ["python", "/app/arrancar.py"]
