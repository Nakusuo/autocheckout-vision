# AutoCaja en la nube: Google Cloud Run (nivel gratuito)

Todo el quiosco (API, reconocimiento e interfaz) corre en un solo contenedor en Cloud Run, con una
dirección `https://autocaja-….us-central1.run.app`:

| Dirección | Para qué |
|---|---|
| `/` | Pantalla del cliente: se abre en el celular quiosco (la cámara funciona porque es https) |
| `/ayuda` | Vista de la caja: solicitudes de ayuda y alertas. Pide la **clave de caja** |
| `/api/pay/notification` | Donde la app Android del comercio manda la notificación de Yape (con su clave) |

> Primero se intentó Hugging Face Spaces, pero desde julio de 2026 los Spaces de Docker ya no son
> gratis para cuentas nuevas. El repositorio privado `Nakusuo/autocaja-modelos` sí se usa: de ahí
> se bajan los modelos y el QR al arrancar.

## Cómo se evita el cobro

Cloud Run pide una tarjeta para activar la cuenta, pero no cobra mientras el uso quede dentro del
nivel gratuito mensual (180 000 vCPU-segundos, 360 000 GiB-segundos, 2 millones de peticiones).

| Tope | Dónde | Por qué |
|---|---|---|
| Cero copias sin visitas (`--min-instances 0`) | `cd.yml` | Mientras nadie lo usa no se cobra nada |
| Una sola copia (`--max-instances 1`) | `cd.yml` | No se multiplica el gasto, y las alertas no se reparten entre copias |
| CPU solo durante cada petición (`--cpu-throttling`) | `cd.yml` | Se paga el tiempo de atender, no el de esperar |
| 1 vCPU y 512 MiB | `cd.yml` | Medido: ~240 MB reconociendo. Alcanza para ~50 h de uso activo de CPU al mes |
| La pantalla cierra su conexión en vivo si el celular apaga la pantalla o cambia de pestaña | `kiosk-ui/src/api.ts` | Cloud Run cobra mientras haya una conexión abierta. Sin esto, una pestaña olvidada gastaría el gratis en ~2 días |
| `/ayuda` no consulta con la pestaña oculta | `AyudaPanel.tsx` | Igual que arriba |
| Imágenes: solo las 2 últimas (~190 MB cada una, comprimidas) | `preparar_gcp.sh` | El almacenamiento gratis es de 0,5 GB |
| Región `us-central1` | `cd.yml` | La de precio más bajo |
| Presupuesto de US$1 con avisos al 50, 90 y 100 % | `preparar_gcp.sh` | Avisa por correo si algo empezara a costar. **No detiene el gasto**: si llega un aviso, borrar el servicio (abajo) |

**Al terminar de presentar:** cerrar la pestaña del quiosco en el celular y la de `/ayuda`.

Para borrar todo (deja de existir cualquier posible costo):

```bash
gcloud run services delete autocaja --region us-central1
gcloud artifacts repositories delete autocaja --location us-central1
```

## Pasos (una sola vez)

### 1. Cuenta y proyecto

1. Entrar a <https://console.cloud.google.com> con tu cuenta de Google y activar la facturación
   (pide la tarjeta; no cobra dentro del nivel gratuito).
2. Crear un proyecto, por ejemplo `autocaja`, y elegirlo arriba en la consola.

### 2. Modelos en Hugging Face (repositorio privado, ya creado)

En `Nakusuo/autocaja-modelos`, **Files → Add file → Upload files**:
`ml/data/models/dinov2-small.onnx`, `ml/data/models/galeria-recuadro.npz` y `privado/yape-qr.png`.
Crear un token de **lectura** en Hugging Face (*Settings → Access Tokens*).

### 3. Preparar Google Cloud

Abrir **Cloud Shell** (el ícono `>_` arriba a la derecha en la consola), subir el archivo
`deploy/nube/preparar_gcp.sh` (menú ⋮ → *Upload*) y correr:

```bash
bash preparar_gcp.sh
```

Pide el token de lectura de Hugging Face (no se ve al pegarlo). Al final muestra:

- tres comandos `gh variable set …` para pegar en la terminal de tu PC (no son secretos);
- la **clave de caja** para entrar a `/ayuda`.

### 4. Primer despliegue

Con el código en `main`: **Actions → CD → Run workflow**. El job «Desplegar el quiosco en Cloud
Run» construye la imagen, la sube y despliega. Al terminar, el resumen del job muestra la dirección.
El primer arranque baja los modelos (~1 min).

## Cómo está armado

- `deploy/nube/Dockerfile`: compila la interfaz (Node) y la copia junto a la API (Python con el
  extra `vision`). La API la sirve (`KIOSK_UI_DIR`), sin nginx, con las mismas cabeceras de
  seguridad (CSP, `X-Frame-Options: DENY`, `Permissions-Policy` con la cámara solo para el sitio).
- `deploy/nube/arrancar.py`: baja del repositorio privado lo que falte y usa el puerto de Cloud Run.
- La API acepta su propia dirección https sin configurarla (Origin = `https://<Host>`) y, en Cloud
  Run (`K_SERVICE`), no arranca sin `KIOSK_CAJA_KEY`.
- GitHub despliega con **Workload Identity Federation**: no hay claves de Google guardadas en
  GitHub, y el permiso solo vale para este repositorio.

## Límites (decirlos en el informe)

- **Arranque en frío:** tras un rato sin visitas, la primera visita tarda (arrancar + bajar los
  modelos, ~1 min). Abrir la dirección unos minutos antes de presentar.
- **Sin disco persistente:** ventas, boletas y alertas se pierden cuando la copia se apaga.
- **Velocidad del reconocimiento en la nube: aún no medida** (en la laptop, ~0,13 s por cuadro).

Probar el mismo contenedor en local:

```bash
docker build -f deploy/nube/Dockerfile -t autocaja-nube .
docker run --rm -p 127.0.0.1:5173:8080 \
  -v "$PWD/ml/data/models:/app/ml/data/models:ro" \
  -v "$PWD/privado:/privado:ro" -e KIOSK_YAPE_QR=/privado/yape-qr.png \
  -e KIOSK_CAJA_KEY=una-clave-de-prueba-larga autocaja-nube
# → http://localhost:5173
```
