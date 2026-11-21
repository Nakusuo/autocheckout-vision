# AutoCaja en Google Cloud Run (nivel gratuito): API + reconocimiento + interfaz en un solo
# contenedor y una sola dirección https. Build desde la raíz del repo:
#   docker build -f deploy/nube/Dockerfile -t autocaja-nube .
# Lo construye y despliega el CD (.github/workflows/cd.yml, job «cloudrun»). Ver docs/NUBE.md.

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

# Usuario sin privilegios.
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
COPY deploy/nube/arrancar.py /app/arrancar.py

USER user
# Cloud Run da el puerto en $PORT (arrancar.py lo pasa a KIOSK_PORT; 8080 por defecto).
# Los modelos y el QR los baja arrancar.py.
ENV KIOSK_HOST=0.0.0.0 \
    KIOSK_PORT=8080 \
    KIOSK_DATA_DIR=/datos \
    KIOSK_MODE=web \
    KIOSK_PAYMENT=yape-qr \
    KIOSK_UI_DIR=/app/ui \
    KIOSK_GALLERY=/app/ml/data/models/galeria-recuadro.npz \
    KIOSK_YAPE_QR=/app/ml/data/models/yape-qr.png
EXPOSE 8080
CMD ["python", "/app/arrancar.py"]
