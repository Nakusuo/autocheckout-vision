# Pasarela de pago simulada (en la nube o local). Build desde la raíz del repo:
#   docker build -f mock-gateway/Dockerfile .
FROM python:3.15-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN useradd --uid 10001 --create-home gateway \
    && mkdir -p /app/keys \
    && chown gateway:gateway /app/keys

WORKDIR /app
COPY mock-gateway/pyproject.toml mock-gateway/pyproject.toml
COPY mock-gateway/src mock-gateway/src
RUN pip install -e ./mock-gateway

USER gateway
# Local: TLS 1.3 propio en :8443. En la nube: GATEWAY_TLS=off y el PaaS fija PORT.
ENV GATEWAY_HOST=0.0.0.0
EXPOSE 8443
CMD ["python", "-m", "gateway"]
