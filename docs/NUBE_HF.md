# AutoCaja en la nube: Hugging Face Spaces (gratis)

Todo el quiosco (API, reconocimiento e interfaz) corre en un solo contenedor en un Space de
Hugging Face. Queda en una dirección `https://<usuario>-autocaja.hf.space`:

| Dirección | Para qué |
|---|---|
| `/` | Pantalla del cliente: se abre en el celular quiosco (la cámara funciona porque es https) |
| `/ayuda` | Vista de la caja: solicitudes de ayuda y alertas. Pide la **clave de caja** |
| `/api/pay/notification` | Donde la app Android del comercio manda la notificación de Yape (con su clave) |

Lo hace el equipo una sola vez. Después, cada merge a `main` con el CI en verde vuelve a desplegar
solo (job `space` de `.github/workflows/cd.yml`).

## Límites del plan gratis (decirlos en el informe)

- **CPU básica (2 vCPU, 16 GB).** El reconocimiento es más lento que en la laptop: medirlo en el
  Space antes de presentar (las líneas «Recuadro: …» del log muestran cada resultado).
- **Se duerme** tras un tiempo sin visitas. Abrir la dirección unos minutos antes de presentar.
- **Sin disco persistente:** ventas, boletas y alertas se pierden al reiniciar el Space.
- **El Space es público** (para que el celular lo abra sin iniciar sesión). Los modelos y el QR
  están en un repositorio **privado** aparte; `/ayuda` y las acciones de caja exigen la clave.

## Pasos

### 1. Cuenta y repositorio privado de modelos

1. Crear una cuenta en <https://huggingface.co>.
2. **New → Model**. Nombre `autocaja-modelos`, **Private**.
3. En ese repositorio, **Files → Add file → Upload files**, subir:
   - `ml/data/models/dinov2-small.onnx`
   - `ml/data/models/galeria-recuadro.npz`
   - `privado/yape-qr.png`

### 2. El Space

1. **New → Space**. Nombre `autocaja`, SDK **Docker** (plantilla *Blank*), hardware **CPU basic
   (free)**, visibilidad **Public**.
2. **Settings → Access Tokens** (de tu cuenta) → crear dos tokens:
   - uno de **lectura** (*Read*) para el Space;
   - uno de **escritura** (*Write*) para que GitHub suba el código.
3. Inventar dos claves largas (en la terminal: `openssl rand -hex 16`, una para cada una).
4. En el Space, **Settings → Variables and secrets**:
   - *Secret* `HF_TOKEN` = el token de **lectura**.
   - *Secret* `KIOSK_CAJA_KEY` = la clave de caja (la que se escribe en `/ayuda`).
   - *Secret* `KIOSK_NOTIFIER_KEY` = la clave de la app de notificaciones.
   - *Variable* `HF_MODELOS` = `<usuario>/autocaja-modelos`.

### 3. GitHub (para el despliegue automático)

En el repositorio: **Settings → Secrets and variables → Actions**:

- *Secret* `HF_TOKEN` = el token de **escritura**. También se puede con
  `gh secret set HF_TOKEN`, que lo pide sin mostrarlo.
- *Variable* `HF_SPACE` = `<usuario>/autocaja`.
- *Variable* `HF_SPACE_URL` = `https://<usuario>-autocaja.hf.space`.

### 4. Primer despliegue

**Actions → CD → Run workflow** (rama `main`). El job «Desplegar el quiosco en Hugging Face
Spaces» sube el código; el Space construye el contenedor (unos minutos) y arranca. En la pestaña
**Logs** del Space se ve «Bajado dinov2-small.onnx…» y luego el quiosco escuchando en el 7860.

## Cómo está armado

- `deploy/hf/Dockerfile`: compila la interfaz (Node) y la copia junto a la API (Python con el
  extra `vision`). La API la sirve (`KIOSK_UI_DIR`), sin nginx, con las mismas cabeceras de
  seguridad (CSP, `X-Frame-Options: DENY`, `Permissions-Policy` con la cámara solo para el sitio).
- `deploy/hf/arrancar.py`: baja del repositorio privado lo que falte y acepta como origen la
  dirección del Space (`SPACE_HOST`, la pone Hugging Face).
- `KIOSK_ORIGINS` sin `KIOSK_CAJA_KEY` no arranca: en internet no se publica una caja sin clave.

Probar el mismo contenedor en local, con los modelos del disco:

```bash
docker build -f deploy/hf/Dockerfile -t autocaja-hf .
docker run --rm -p 127.0.0.1:5173:7860 \
  -v "$PWD/ml/data/models:/app/ml/data/models:ro" \
  -v "$PWD/privado:/privado:ro" -e KIOSK_YAPE_QR=/privado/yape-qr.png \
  -e KIOSK_CAJA_KEY=una-clave-de-prueba-larga autocaja-hf
# → http://localhost:5173 (el origen local que acepta la API; en localhost la cámara va sin https)
```
