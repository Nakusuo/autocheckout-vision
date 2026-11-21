# API del quiosco (edge). Build desde la raíz del repo:
#   docker build -f kiosk-api/Dockerfile .
# Para el modo cámara: --build-arg EXTRAS=dev,vision (o EXTRAS=vision).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Usuario sin privilegios; /datos guarda kiosk.db, boletas, sesiones y el log (un volumen).
RUN useradd --uid 10001 --create-home kiosk \
    && mkdir -p /app/keys /datos \
    && chown kiosk:kiosk /app/keys /datos

# Misma estructura que el repo: el código busca catalog/ y keys/ tres niveles arriba del paquete.
WORKDIR /app
COPY catalog/products.csv catalog/products.csv
COPY kiosk-api/pyproject.toml kiosk-api/pyproject.toml
COPY kiosk-api/src kiosk-api/src
ARG EXTRAS=""
RUN pip install -e "./kiosk-api${EXTRAS:+[$EXTRAS]}"

USER kiosk
ENV KIOSK_HOST=0.0.0.0 \
    KIOSK_PORT=8000 \
    KIOSK_DATA_DIR=/datos \
    KIOSK_MODE=sim
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request as u; u.urlopen('http://127.0.0.1:8000/api/state', timeout=2)"]
CMD ["python", "-m", "kiosk"]
