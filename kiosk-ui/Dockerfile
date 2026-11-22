# Interfaz del quiosco: se compila con Node y se sirve con nginx (sin root).
# Build desde la raíz del repo:  docker build -f kiosk-ui/Dockerfile .
FROM node:22-alpine AS build
WORKDIR /ui
COPY kiosk-ui/package.json kiosk-ui/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY kiosk-ui/ ./
RUN npm run build

FROM nginxinc/nginx-unprivileged:1.31-alpine
# nginx reemplaza ${KIOSK_API} al arrancar (plantillas de la imagen oficial).
ENV KIOSK_API=kiosk-api:8000
COPY kiosk-ui/nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /ui/dist /usr/share/nginx/html
EXPOSE 8080
HEALTHCHECK --interval=10s --timeout=3s --retries=3 \
    CMD ["wget", "-q", "-O", "/dev/null", "http://127.0.0.1:8080/"]
