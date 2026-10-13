# Informe de cambios locales: activación de cámara y corrección del flujo de compra

**Proyecto:** AutoCaja / `autocheckout-vision`

**Destinatarios:** equipo de desarrollo

**Fecha del informe:** 13 de octubre de 2026, zona horaria de Lima

**Repositorio:** https://github.com/Nakusuo/autocheckout-vision

**Rama original de la intervención:** `main`

**Rama local de entrega:** `fix/webcam-confirmacion-laptop`

**Commit base de las correcciones:** `5eafc4f09b1896e743b0e091f69c820f51b4b150`

**Base remota integrada posteriormente:** `origin/main`, commit `58b063b00446cbbc8c3dd7b1a37266ede1682663`, que contiene `origin/develop` (`0da1210aafdbf53f01dce88ac2b5ea5d0e527122`).

**Estado de entrega:** correcciones guardadas en commits de una rama local independiente e integradas con la actualización remota; no publicadas en GitHub. Ver el apartado 12 para las pruebas posteriores a esta integración.

## 1. Resumen para el equipo

Se preparó el proyecto en una laptop Windows, se descargaron los modelos necesarios, se importaron las fotografías de los productos y se generó la galería de reconocimiento. Después se activó la webcam y se corrigió el flujo que impedía confirmar una compra aunque el producto ya apareciera reconocido en la lista.

El comportamiento final solicitado para la prueba es el siguiente:

1. La cámara permanece activa en la pantalla inicial para aprender el fondo, pero no agrega productos al carrito antes de INICIAR.
2. Al iniciar la compra, la lista está vacía y CONFIRMAR permanece deshabilitado.
3. Solo se acumulan productos reconocidos que existen en el catálogo.
4. Después del primer producto registrado, se permite confirmar, siempre que se respeten el máximo de tres productos y la validación de peso si se activa una balanza.
5. En modo cámara real, las detecciones desconocidas no se guardan en el carrito, no generan la alerta bloqueante del cliente y no bloquean lo ya reconocido. Después de integrar la actualización del equipo, se conserva su alerta de seguridad en `/caja`, sin impedir la confirmación del cliente.
6. CONFIRMAR libera físicamente la webcam y mantiene fija la lista durante la confirmación, el pago y la pantalla del ticket.
7. CORREGIR vuelve a abrir la cámara para seguir escaneando. Cancelar o regresar al inicio después del ticket también la vuelve a abrir.

**Decisión funcional que el equipo debe tener presente:** ignorar detecciones desconocidas es el comportamiento solicitado para esta prueba, no una mejora de la precisión del modelo. Un producto no reconocido no se cobra. Sin balanza, esta política permite que existan productos fuera de la lista sin impedir el pago.

## 2. Situación inicial y diagnóstico

### 2.1. El soporte de cámara ya estaba en el repositorio

Se compararon las ramas remotas `main` y `develop`. Ambas contenían el arranque `KIOSK_MODE=camera`, el reconocimiento por parecido y el acceso a la webcam mediante OpenCV. No era necesario cambiar de rama para disponer de esa funcionalidad.

La instalación local estaba ejecutándose con el detector simulado. Además, al clonar no se habían obtenido las fotografías, los pesos ONNX ni la galería, porque `ml/data/` y los modelos están excluidos de Git.

### 2.2. Un desconocido se acumulaba como si fuera una compra

En `KioskService._register_view()`, las detecciones nuevas se añadían directamente a `_scanned`, incluyendo `DESCONOCIDO`. Después, `_cart()` construía el carrito a partir de ese contador acumulado.

Esto permitía reproducir la siguiente secuencia:

```text
La cámara devuelve DESCONOCIDO durante tres cuadros estables
    → DESCONOCIDO queda guardado en el contador de escaneos
La cámara reconoce VIZZIO-19
    → se agrega Vizzio 19 g a la lista y el total muestra S/ 3.00
El producto se retira de la cámara
    → el desconocido anterior sigue dentro del carrito
Se intenta confirmar
    → la API rechaza la acción por cart.unknown_skus
```

La interfaz mostraba un producto válido, pero la entrada desconocida permanecía oculta: `build_cart()` separa los SKU desconocidos de las líneas visibles. La alerta y el bloqueo eran, por tanto, compatibles con una lista que aparentemente contenía solo un Vizzio.

La reproducción se hizo con el servicio real en memoria y lecturas controladas. Se comprobó también que recalibrar la cámara no eliminaba un desconocido ya acumulado; cancelar la compra sí limpiaba el carrito.

### 2.3. El panel simulado mostraba una bandeja vacía en modo cámara

La captura inicial correspondía al panel `/sim`. Ese panel consulta `/sim/tray` y `/sim/catalog`, pero la API no registra esas rutas al arrancar con cámara real. Se verificaron respuestas HTTP 404.

En `SimPanel.tsx`, el estado de bandeja comienza como una lista vacía y el error de actualización de `/sim/tray` se ignora. Por eso podía aparecer «0 en la bandeja» al mismo tiempo que la lista de compra mostraba un producto reconocido.

Ese contador no representa una medición física de la bandeja en modo cámara real y no era la causa del bloqueo. Para la prueba real se usan `/` y `/caja`. No se modificó el panel `/sim` en esta intervención.

## 3. Preparación del entorno local

### 3.1. Software y dependencias

Se instaló Python 3.12.10 desde el paquete oficial de Python mediante `winget`, con alcance de usuario. Git y Node.js ya estaban disponibles.

| Componente | Versión comprobada en la laptop |
|---|---|
| Python | 3.12.10 |
| Node.js | 24.21.0 |
| npm | 11.19.0 |
| OpenCV | 5.0.0, paquete `opencv-python-headless` |
| NumPy | 2.5.4 |
| ONNX Runtime | 1.31.0 |

Se crearon entornos virtuales independientes en `mock-gateway/.venv`, `kiosk-api/.venv` y `ml/.venv`.

Los extras utilizados fueron:

- `mock-gateway`: `.[dev]`.
- `kiosk-api`: `.[dev,vision]`.
- `ml`: `.[dev,bench,heic]`, incluyendo conversión de fotografías HEIC con Pillow y pillow-heif.
- `kiosk-ui`: instalación desde `package-lock.json` con `npm ci --ignore-scripts`.

Las dependencias Python externas se instalaron como ruedas binarias mediante `--only-binary=:all:`. Se construyeron los paquetes editables locales del propio proyecto. No se añadió una dependencia nueva a los manifiestos del repositorio.

También se instalaron los componentes de Chromium requeridos por Playwright para las pruebas integradas del sistema simulado.

### 3.2. Modelos descargados

Los archivos se guardaron en `ml/data/models/`:

| Archivo | Tamaño en bytes | Función |
|---|---:|---|
| `dinov2-small.onnx` | 88 532 934 | Calcula la descripción visual que se compara con la galería. |
| `silueta.onnx` | 44 173 029 | Separa el producto del fondo al preparar las fotografías de referencia. |
| `galeria.npz` | 333 249 | Galería generada localmente con los productos del catálogo. |

Fuentes utilizadas:

- DINOv2: [onnx-community/dinov2-small](https://huggingface.co/onnx-community/dinov2-small). Se descargó `onnx/model.onnx` de la revisión `8b1f705a3a7f6f062f6bdd21986c1583d3ef105d`.
- Silueta: [archivo publicado por rembg](https://github.com/danielgatis/rembg/releases/download/v0.0.0/silueta.onnx).

SHA-256 de los archivos locales comprobados al preparar este informe:

```text
dinov2-small.onnx
f22797eabf810a75e41de68d378541ebea372122b25c4ce3ef25ff618250c20a

silueta.onnx
75da6c8d2f8096ec743d071951be73b4a8bc7b3e51d9a6625d63644f90ffeedb
```

Para DINOv2 se verificó la coincidencia del SHA-256 con los metadatos LFS del repositorio de origen. Para Silueta se comprobó el tamaño publicado en GitHub y se calculó el hash local; la respuesta de la versión publicada no proporcionaba un digest para compararlo.

Se comprobó la carga e inferencia de ambos modelos con ONNX Runtime. DINOv2 devolvió una descripción finita y normalizada de 384 componentes; Silueta devolvió una máscara de tamaño válido. No se entrenó YOLO ni se descargó un modelo YOLO para sustituir el reconocimiento por parecido.

### 3.3. Fotografías y generación de la galería

Las fotografías se obtuvieron de la [carpeta de Drive proporcionada para el proyecto](https://drive.google.com/drive/folders/1WIRorq9X8Te4yIhvm5A1OxWHl2ma87yS).

Se descargaron únicamente las carpetas correspondientes a los once productos del catálogo. No se modificaron los archivos del Drive.

Los originales quedaron en `ml/data/drive/AutoCaja-dataset/`. Se utilizó `mltools.importar` para generar `ml/data/raw/<SKU>/`, convertir HEIC a JPEG y normalizar los nombres de carpeta. Por ejemplo, `KRpiña-3,03L` pasó a `KRPINA-3.03L`.

| SKU | Fotografías importadas |
|---|---:|
| CANCUN-33 | 4 |
| CASINO-43 | 5 |
| CHOCMAN-39 | 5 |
| CLUBSOCIAL-24 | 4 |
| GLACITAS-30G | 8 |
| GUARANA-450 | 6 |
| KRPINA-3.03L | 5 |
| MOROCHAS-30 | 5 |
| RITZ-20 | 4 |
| VIZZIO-19 | 5 |
| YOFRESH-190 | 5 |
| **Total** | **56** |

La galería se generó con `python -m kiosk.recognizer galeria`. Contiene 224 referencias, correspondientes a cuatro rotaciones de cada fotografía, y utiliza el tamaño de entrada de 140 píxeles establecido por el proyecto.

Se verificaron los once SKU, las 56 fotografías de origen y la ausencia de valores no finitos en los vectores.

La evaluación que excluye la propia fotografía de referencia dio **49/56 aciertos, equivalentes a 87,5 %**; la consola lo redondea a 88 %. Las cinco fotografías de Vizzio se clasificaron correctamente frente a las otras referencias.

Este resultado evalúa las fotos disponibles. No mide la precisión de la webcam bajo las condiciones reales de la laptop.

### 3.4. Comprobaciones de seguridad efectuadas durante la preparación

Se revisaron manifiestos, comandos de arranque y posibles scripts de instalación antes de ejecutarlos. `npm audit` reportó cero vulnerabilidades conocidas en el momento de la instalación. Microsoft Defender estaba activo y los escaneos realizados sobre el proyecto, dependencias y datos descargados no reportaron amenazas.

Estas comprobaciones describen lo realizado durante la sesión; no equivalen a una auditoría exhaustiva de todos los paquetes ni a una garantía de ausencia total de riesgo.

## 4. Cambios de código implementados

### 4.1. `kiosk-api/src/kiosk/service.py`: carrito y ciclo de cámara

**Registro de productos.** `_register_view()` filtra las nuevas detecciones con `catalog.get(sku)`. Solo se acumulan los SKU existentes en el catálogo; `DESCONOCIDO` y cualquier etiqueta ajena al catálogo dejan de guardarse como productos comprados.

**Construcción del carrito.** `_cart()` diferencia el funcionamiento del detector con ciclo de cámara del simulador. Cuando el detector dispone de `close()`, la compra se construye con los productos registrados acumulados y se ignoran los desconocidos de la vista actual. En el caso sin esos hooks, los desconocidos de la vista actual siguen formando parte de la validación del carrito, pero no se acumulan permanentemente.

**Alerta inicial.** La alerta por SKU desconocido exige que ya exista al menos un producto registrado en el carrito. En el modo cámara final no se incorpora un desconocido al carrito, por lo que esa alerta no aparece por ese motivo.

**Apertura y cierre por estado.** El constructor obtiene los métodos opcionales `open()` y `close()` del detector. `_do()` coordina esos métodos después de cada transición de la máquina de estados. La decisión se toma en el backend; no depende de que el navegador esconda una imagen o cierre una pestaña.

**Lecturas permitidas.** `wants_reading()` mantiene las lecturas de cámara en W1 y W2, y las detiene en W3 para detectores con cierre de cámara. En modo simulado conserva la lectura en W3 y el comportamiento previo de reabrir el escaneo si entra otro producto.

**Lista congelada y cuadros tardíos.** Si una lectura que comenzó antes de confirmar termina después de pasar a W3, `tick()` descarta esa lectura para el modo cámara. `read_sensors()` evita ejecutar el detector cuando la cámara no debe leerse y utiliza la última vista registrada. Así se evita agregar productos tardíos o reabrir W2 automáticamente durante la confirmación real.

**Balanza.** La lectura de peso se conserva cuando hay una balanza configurada. Cerrar la webcam no desactiva la comprobación de peso ni habilita un pago con peso incorrecto.

### 4.2. `kiosk-api/src/kiosk/vision.py`: cierre físico y reapertura

`CameraSource` ahora conserva el índice del dispositivo y proporciona un método `open()` explícito. Las operaciones de abrir, leer y cerrar se protegen con `threading.Lock`.

Cambios concretos:

- `open()` no vuelve a abrir un dispositivo ya abierto.
- Si OpenCV no logra abrirlo, libera el recurso fallido y comunica el error.
- `read()` falla con un error claro si la cámara está apagada; una lectura no la reabre por su cuenta.
- `close()` ejecuta `VideoCapture.release()` y elimina la referencia al dispositivo activo.
- Cerrar una cámara ya cerrada es seguro.
- Una reapertura posterior crea una captura nueva con el mismo índice.

`YoloOnnxDetector` incorpora `open()` y `close()` que delegan en la fuente cuando esta admite esos métodos. Esto permite utilizar el mismo control de cámara con el detector YOLO existente, sin cambiar su algoritmo de inferencia.

### 4.3. `kiosk-api/src/kiosk/recognizer.py`: integración con el reconocedor por parecido

`SimilarityDetector` incorpora `open()` y `close()` para delegar el control a su fuente de cuadros. Utiliza el bloqueo que ya protegía el reconocimiento y la recalibración, evitando cerrar la fuente mientras ese detector procesa una lectura.

El reconocedor sigue devolviendo `DESCONOCIDO` cuando no encuentra suficiente parecido o cuando detecta más de una región relevante. El cambio de política se aplica en `KioskService`, que ignora ese resultado en la prueba con cámara. No se redujo el umbral de reconocimiento para hacer que imágenes dudosas pasaran como productos válidos.

### 4.4. Interfaz y rutas HTTP

No fue necesario modificar componentes React ni añadir endpoints. La interfaz ya habilitaba CONFIRMAR cuando había productos y no existía una alerta bloqueante; el backend ahora entrega el estado correspondiente al flujo solicitado.

Se reutilizan `/api/start`, `/api/confirm`, `/api/correct`, `/api/cancel`, `/api/pay` y `/api/recalibrate`.

Se mantiene la obligación de tener de uno a tres productos registrados antes de confirmar. No se modificaron la generación del QR, la validación TLS/JWT, las boletas simuladas ni la persistencia del catálogo.

## 5. Flujo final por pantalla

| Pantalla / estado | Webcam | Lista y acciones |
|---|---|---|
| W1 / IDLE | Abierta | Aprende el fondo; no agrega compras antes de INICIAR. |
| W2 / SCANNING, sin productos | Abierta | Lista vacía; CONFIRMAR deshabilitado. |
| W2 / SCANNING, con 1–3 productos registrados | Abierta | Permite agregar más, quitar unidades, cancelar o confirmar; desconocidos ignorados. |
| W3 / CONFIRMING | Cerrada | Lista congelada; permite PAGAR, CORREGIR o cancelar. |
| QR / PAYING | Cerrada | Espera confirmación del pago; puede cancelarse. |
| W4 / PAID | Cerrada | Muestra el ticket; al regresar automáticamente a W1 vuelve a abrirse. |
| CORREGIR → W2 | Reabierta | Conserva la lista y permite seguir escaneando. |
| CANCELAR → W1 | Reabierta | Limpia la compra y regresa al inicio. |

Si el pago vence y vuelve a W3, la cámara sigue cerrada. El retorno automático después del ticket conserva el plazo existente de diez segundos.

El campo `camera` del snapshot no informa si el dispositivo está abierto: actualmente indica que el detector permite recalibrar. Puede seguir siendo `true` en W3 aunque la webcam esté físicamente cerrada. No debe usarse como prueba del estado del LED o del recurso de OpenCV.

## 6. Archivos modificados

| Archivo | Motivo |
|---|---|
| `kiosk-api/src/kiosk/service.py` | Filtrado de productos, política de desconocidos, control de cámara y descarte de cuadros tardíos. |
| `kiosk-api/src/kiosk/vision.py` | Apertura/cierre explícitos y seguros de la webcam; hooks del detector YOLO. |
| `kiosk-api/src/kiosk/recognizer.py` | Hooks de apertura/cierre del reconocedor por parecido. |
| `kiosk-api/tests/test_service.py` | Regresiones del carrito y del ciclo de cámara; adaptación del doble de cámara. |
| `kiosk-api/tests/test_app.py` | Regresión de confirmación y pago sobre HTTP después de un desconocido temporal. |
| `kiosk-api/tests/test_vision.py` | Cierre repetido, lectura con cámara cerrada y reapertura explícita. |
| `README.md` | Explicación del flujo final de la prueba real. |
| `docs/ESTADO.md` | Diferencia entre confirmación con cámara cerrada y comportamiento del simulador. |
| `docs/ml/reconocimiento.md` | Política de desconocidos, ciclo de cámara y límite de cobro. |
| `docs/INFORME_CAMBIOS_CAMARA_2026-10-13.md` | Este informe de entrega. |

Los modelos, la galería, las fotografías, los entornos virtuales, las claves de desarrollo y las bases/boletas locales son recursos generados o instalados fuera de Git. Enviar únicamente este Markdown no transfiere esos recursos ni los cambios de código.

## 7. Verificación realizada

### 7.1. Pruebas automatizadas antes de integrar la actualización remota

| Comprobación | Resultado registrado en la sesión de implementación |
|---|---|
| Suite completa de `kiosk-api` | **158 pruebas aprobadas**. |
| Suite de `kiosk-ui` | **25 pruebas aprobadas**. |
| Total API + UI después del último cambio | **183 pruebas aprobadas**. |
| Ruff en código y pruebas de la API | Sin errores. |
| Bandit en `kiosk-api/src` | Sin hallazgos reportados. |
| `git diff --check` | Sin errores de espacios en el diff. |

La API tenía 146 pruebas en la instalación base; la implementación final incorpora doce casos adicionales contando las parametrizaciones. Las pruebas de regresión se ejecutaron primero contra el comportamiento anterior y fallaron por las causas que se pretendía corregir.

Casos cubiertos por las nuevas pruebas:

1. La cámara no agrega compras antes de INICIAR y un inicio sin producto registrado no permite confirmar ni pagar.
2. Un desconocido previo, incluyendo una etiqueta ajena al catálogo, no bloquea la confirmación posterior de un producto válido.
3. Un desconocido después del primer producto no bloquea la confirmación en modo cámara.
4. Confirmar cierra la cámara, congela la lista y descarta cuadros o errores tardíos.
5. La cámara permanece cerrada al pasar a QR.
6. Cancelar desde W3 o QR limpia el carrito y vuelve a abrir la cámara.
7. CORREGIR abre la cámara y no vuelve a sumar inmediatamente el mismo producto que seguía registrado en la vista.
8. Después de un pago confirmado, la cámara permanece cerrada en el ticket y vuelve a abrirse al regresar a W1.
9. Con balanza habilitada, W3 sigue detectando diferencias de peso aunque la webcam esté cerrada.
10. La API HTTP vuelve a permitir confirmar y crear el pago tras una detección desconocida temporal.
11. `CameraSource` admite cierre repetido, rechaza lecturas apagada y puede reabrirse explícitamente.

La salida de pytest conservó dos advertencias de dependencias: una de deprecación del cliente de pruebas de Starlette y otra por una clave HMAC deliberadamente corta en una prueba de rechazo de JWT. No fueron fallos de los casos ni se utilizaron claves reales de pago.

### 7.2. Pruebas previas de instalación

Durante la preparación inicial también se aprobaron 13 pruebas de `mock-gateway`, 39 de `ml` y tres pruebas Playwright del sistema simulado, además de la compilación y lint de la UI. Esos resultados corresponden a esa fase; las tres e2e no se repitieron después del último cambio de ciclo de cámara.

### 7.3. Comprobación con el dispositivo físico

Windows reconoció la webcam `USB2.0 HD UVC WebCam`. Se recibieron cuadros de **640 × 480**.

Se realizó una comprobación aislada con `CameraSource`, `SimilarityDetector` y `KioskService` reales, la galería descargada y una pasarela de pruebas en memoria:

1. Se abrió la webcam y se recibió una lectura real.
2. Se proporcionaron al servicio lecturas controladas de un SKU registrado para llegar a la confirmación de forma repetible.
3. Al confirmar, se comprobó que la referencia de captura activa quedaba vacía y que el objeto `VideoCapture` anterior ya no estaba abierto.
4. Se comprobó que no se podían leer cuadros con la cámara cerrada y que una lectura tardía no alteraba la compra.
5. Al cancelar, se verificó una reapertura real y la recepción de otro cuadro.

Esta comprobación valida el cierre y la reapertura del hardware. **No sustituye una compra completa en la que el usuario presenta físicamente un producto y el modelo lo reconoce.** No se guardaron imágenes de la webcam durante estas comprobaciones.

## 8. Reproducción del entorno por el equipo

Los siguientes comandos son para PowerShell en Windows. Abrir cada terminal desde la raíz del repositorio. Los puertos 5173, 8000 y 8443 deben estar disponibles; no iniciar dos instancias de la API que intenten usar la misma webcam.

### 8.1. Instalación inicial, si aún faltan los entornos

```powershell
python -m venv mock-gateway/.venv
& ./mock-gateway/.venv/Scripts/python.exe -m pip install --only-binary=:all: -e './mock-gateway[dev]'

python -m venv kiosk-api/.venv
& ./kiosk-api/.venv/Scripts/python.exe -m pip install --only-binary=:all: -e './kiosk-api[dev,vision]'

python -m venv ml/.venv
& ./ml/.venv/Scripts/python.exe -m pip install --only-binary=:all: -e './ml[dev,bench,heic]'

Set-Location ./kiosk-ui
npm ci --ignore-scripts
```

Requisitos: Python 3.12 y Node.js 22 o superior, según el README. Usar un ejecutable de Python real; en Windows el alias de Microsoft Store puede existir sin que Python esté instalado.

Las dependencias Python no están fijadas mediante un archivo de bloqueo en el proyecto base. Una instalación futura puede resolver versiones diferentes; el equipo debe ejecutar sus pruebas con esas versiones.

### 8.2. Recursos de reconocimiento

Obtener los dos modelos y las fotografías indicados en la sección 3, respetando los nombres de archivo. Si se proporciona `galeria.npz` ya generada, el arranque del reconocimiento por parecido necesita la galería y DINOv2; Silueta y las fotos son necesarias para regenerarla.

Desde la raíz del repositorio, con el dataset local disponible:

```powershell
& ./ml/.venv/Scripts/python.exe -m mltools.importar './ml/data/drive/AutoCaja-dataset'
& ./ml/.venv/Scripts/python.exe -m mltools.dataset_check --min 4

Set-Location ./kiosk-api
& ./.venv/Scripts/python.exe -m kiosk.recognizer galeria
& ./.venv/Scripts/python.exe -m kiosk.recognizer evaluar
```

`--min 4` comprueba el mínimo de fotos usado en esta galería por parecido. No significa que cuatro fotografías sean suficientes para entrenar YOLO; el verificador conserva otro mínimo por defecto para ese camino de entrenamiento.

### 8.3. Terminal 1: pasarela simulada

```powershell
Set-Location ./mock-gateway
$env:GATEWAY_API_KEY = 'REEMPLAZAR_POR_UNA_CLAVE_LOCAL_LARGA'
& ./.venv/Scripts/python.exe -m gateway.devkeys
& ./.venv/Scripts/python.exe -m gateway
```

### 8.4. Terminal 2: API con webcam real

```powershell
Set-Location ./kiosk-api
$env:GATEWAY_API_KEY = 'REEMPLAZAR_POR_LA_MISMA_CLAVE_DE_LA_PASARELA'
$env:PYTHONUTF8 = '1'
$env:KIOSK_MODE = 'camera'
$env:KIOSK_GALLERY = '../ml/data/models/galeria.npz'
$env:KIOSK_CAMERA = '0'
$env:KIOSK_SCALE = 'off'
& ./.venv/Scripts/python.exe -m kiosk
```

Los dos valores ilustrativos de `GATEWAY_API_KEY` deben reemplazarse por **la misma clave** en las dos terminales. No se incluye en este informe la clave temporal utilizada en la laptop. Los archivos `.env` no sustituyen la configuración de las variables en estos comandos: el arranque actual lee `os.environ` y no carga automáticamente ese archivo.

### 8.5. Terminal 3: interfaz

```powershell
Set-Location ./kiosk-ui
npm run dev
```

Abrir:

- `http://localhost:5173/`: quiosco para el cliente.
- `http://localhost:5173/caja`: ayuda y recalibración.
- `/sim`: únicamente para el modo simulado; sus controles de bandeja no funcionan con la API en modo cámara.

### 8.6. Comandos de verificación del código

Desde `kiosk-api`:

```powershell
& ./.venv/Scripts/python.exe -m pytest -q
& ./.venv/Scripts/ruff.exe check src tests
& ./.venv/Scripts/bandit.exe -q -r src
```

Desde `kiosk-ui`:

```powershell
npm test -- --run --maxWorkers=1
```

Cada equipo debe detenerse ante un comando con error y revisar su salida; los bloques son instrucciones de reproducción, no un instalador automático con gestión de fallos.

## 9. Prueba de aceptación que debe repetir el equipo

1. Fijar la webcam apuntando a la zona de escaneo, con luz estable y sin objetos sobre ella.
2. Si se movió la cámara o se inició con un objeto visible, recalibrar desde `/caja` con la zona vacía.
3. Iniciar una compra y comprobar que CONFIRMAR permanece deshabilitado sin productos registrados.
4. Presentar un producto del catálogo, retirar la mano y esperar la estabilidad de la detección.
5. Comprobar nombre, cantidad y precio; retirar el producto y verificar que CONFIRMAR continúa habilitado.
6. Confirmar y comprobar el apagado del dispositivo. La lista debe permanecer fija aunque se muevan objetos delante de la webcam.
7. Usar CORREGIR y comprobar que se abre la webcam y se conserva la lista.
8. Repetir la confirmación y cancelar, tanto desde W3 como desde QR; comprobar el retorno a W1 y la reapertura.
9. Completar un pago **simulado**, revisar el ticket y comprobar la reapertura al regresar a W1.
10. Repetir con los once productos, distintas orientaciones y condiciones de luz; registrar errores de identificación, omisiones o cantidades duplicadas.

Para esta prueba de pago real en la interfaz con webcam, la pasarela sigue siendo simulada: no se conectaron credenciales ni cuentas de Yape/Plin reales.

## 10. Límites y trabajo pendiente

- La precisión del modelo no fue corregida mediante entrenamiento. Los 49/56 aciertos de la galería no demuestran una precisión equivalente en vivo.
- Las manos, el fondo, los reflejos y los cambios de luz pueden seguir causando `DESCONOCIDO`. El cambio impide que esos resultados bloqueen el flujo; no elimina su origen visual.
- Sin balanza y con desconocidos ignorados, no hay garantía de que todo producto físico sea cobrado. La lista debe revisarse y esta política debe evaluarse antes de cualquier uso con clientes.
- En cámara real se eliminó la vigilancia de nuevos productos durante W3: después de confirmar, se requiere CORREGIR para añadirlos. Es una modificación deliberada del comportamiento anterior, no un detalle técnico sin efecto funcional.
- La prueba de CORREGIR cubre que no se vuelva a sumar inmediatamente la misma vista conservada. No es una garantía general contra duplicados cuando cambia la clasificación al girar o retirar un producto; eso requiere pruebas físicas adicionales.
- La corrección local no añadió previsualización de video en React ni un recorte fijo de zona de escaneo. La actualización remota integrada sí incorpora `KIOSK_ZONE` para configurar un recorte y `KIOSK_HANDS` para filtrar manos. La pantalla sigue mostrando la lista reconocida, no los cuadros de la webcam.
- No se implementó una balanza física. La configuración utilizada es `KIOSK_SCALE=off`; la lógica de peso disponible se conserva.
- No se ejecutó un benchmark completo de latencia en vivo ni una campaña de pruebas con usuarios después del último cambio.
- No se publicaron los cambios en `main` o `develop`. La versión remota no recibe estas modificaciones por enviar este informe.

## 11. Entrega e integración recomendadas

El equipo debe recibir el diff de los archivos indicados, además de este informe, y revisar especialmente la política de ignorar desconocidos y el apagado de cámara durante W3. Conviene integrar las modificaciones mediante una rama y un pull request, ejecutar el CI y repetir la prueba de aceptación física antes de actualizar la versión de la demo.

Los recursos de `ml/data/` necesitan una entrega separada o un procedimiento de descarga y generación. La galería debe corresponder al catálogo y al tamaño de entrada del modelo. No subir al repositorio las claves de `keys/`, valores reales de API ni fotografías fuera del alcance acordado para el dataset.

**Resultado de la intervención:** la laptop quedó preparada para reconocimiento por parecido con webcam y el flujo de confirmación solicitado quedó implementado y probado a nivel de servicio, API, interfaz y ciclo físico del dispositivo. La aceptación final del reconocimiento de productos en vivo queda pendiente de la prueba del usuario/equipo.

## 12. Guardado en rama aparte e integración de main/develop

### 12.1. Protección y trazabilidad de los cambios

Por solicitud del usuario, se guardó la intervención en `fix/webcam-confirmacion-laptop`, sin mover la rama local `main` ni modificar o publicar cambios sobre `main` o `develop` en GitHub. La identidad de los commits se configuró únicamente en este repositorio, con nombre `walter-11` y el correo proporcionado por el usuario; no se cambió la configuración global de Git.

Se creó el commit de respaldo `8ea85d1a3f9eb987df58dd0dcceacf8bcab5289b` y se conservó mediante la rama local `backup/webcam-antes-actualizacion-2026-10-13`. Esa rama permite recuperar la intervención anterior a la actualización.

Se descargaron las referencias remotas de `main` y `develop`. El `main` descargado ya contiene todo `develop`, por lo que se usó como base de integración sin hacer una segunda mezcla redundante. El commit local de cámara se reaplicó sobre esta base exclusivamente en la rama de entrega. El hash del commit cambia al reaplicarlo; el original permanece en la rama de respaldo.

### 12.2. Resolución de incompatibilidades

La integración presentó conflictos en `README.md`, `docs/ESTADO.md`, `docs/ml/reconocimiento.md`, `service.py`, `test_app.py` y `test_service.py`. Se combinaron manualmente los cambios, conservando tanto las correcciones locales como las mejoras remotas:

- Zona de escaneo configurable y filtrado de manos del reconocedor.
- Validación de entradas HTTP, límites de solicitudes, historial de ventas y rotación de registros.
- Alertas de seguridad para caja: un desconocido puede quedar registrado para revisión, aunque no bloquee al cliente en modo webcam.
- Cámara cerrada desde CONFIRMAR y carrito congelado durante confirmación, pago y ticket; reapertura al corregir, cancelar o volver al inicio.
- Validación de desconocidos y reapertura de W2 conservadas en el simulador, que no tiene los hooks físicos de cámara.
- Ordenamiento estable de las líneas del carrito.
- Pruebas del equipo y pruebas locales conservadas, sin sustituir un archivo completo por una de las versiones.

Se añadió el tipo explícito `cv2.VideoCapture | None` para que el cierre y reapertura de la cámara pasen el nuevo control de tipos. Las pruebas de integración usan una cámara grabada con estado abierto/cerrado y comprueban el bloqueo antes del primer producto, la confirmación después de reconocerlo aunque aparezca un desconocido, la lista congelada y la reapertura por corrección/cancelación. Estas pruebas no sustituyen una prueba física de reconocimiento con los productos de la tienda.

### 12.3. Verificación después de integrar

| Verificación | Resultado |
|---|---|
| Suite de API con cobertura de ramas | 261 pruebas aprobadas; cobertura total 96,37 %, superior al mínimo del CI de 90 %. |
| Suite de interfaz | 91 pruebas aprobadas. |
| Suite de pasarela simulada | 13 pruebas aprobadas. |
| Suite de herramientas ML | 39 pruebas aprobadas. |
| Playwright de punta a punta, modo simulado | 4 pruebas aprobadas. |
| Ruff sobre código y pruebas de API | Sin errores. |
| Mypy sobre los 17 archivos de la API | Sin errores. |
| Bandit con la configuración del paquete | Sin hallazgos. |
| Lint y compilación de la interfaz | Correctos. |

Total de las suites anteriores: **408 pruebas aprobadas**. Playwright arranca sus servicios locales de prueba en modo simulado y verifica compra, peso, ayuda, cancelación y pago por QR, también sin balanza. No es una validación del reconocimiento de productos por webcam física. En Windows se observaron mensajes `ConnectionResetError` al cerrar conexiones y avisos sobre variables de color de consola, sin fallos en las cuatro pruebas. Pytest conserva los avisos de deprecación de Starlette/httpx y de clave corta usados en una prueba deliberada de rechazo de un token inseguro.

Se reinstalaron las dependencias de la interfaz desde el lockfile actualizado usando `npm ci --ignore-scripts`, y se actualizaron los extras de desarrollo/visión de la API dentro de su entorno virtual. No se aplicó `npm audit fix` ni se cambió el lockfile del equipo automáticamente.

La auditoría completa de npm reportó dos paquetes con vulnerabilidades moderadas: `qs@6.15.1` y su consumidor `typed-rest-client@2.3.1`, incorporados transitivamente por `@stryker-mutator/core@10.0.0`, una herramienta de desarrollo. `npm audit --omit=dev` no reportó vulnerabilidades de producción y el umbral de CI `npm audit --audit-level=high` pasó. Los avisos moderados siguen pendientes de revisión por el equipo; no equivalen a una certificación de ausencia de malware.

La integración no publica la rama en GitHub ni incorpora modelos, fotos o claves al historial. Para compartir el código con el equipo hace falta publicar esta rama o entregar su diff; no se realizó un push a las ramas compartidas.
