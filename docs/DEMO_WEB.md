# Demo web: «el celular es la máquina»

La idea de la demo: el quiosco corre en un celular (o, por ahora, en el navegador de la laptop). La cámara reconoce los productos, el cliente los agrega con un toque, paga escaneando el **QR de Yape del comercio** y la pantalla muestra **«Cobro exitoso»** con la boleta.

Ahora todo corre en la web y el pago está **simulado**. Después se hará la app (React Native, con un backend como Firebase) que detecte los yapes de verdad (§5).

> **Qué se probó y qué no** (2026-11-19). Se probó el flujo completo en Docker: sugerencia de productos a partir de fotos, agregar, pagar, rechazo por monto distinto, aceptación con el monto exacto y boleta. Se sacaron capturas con la cámara de prueba de Chromium. Hay 393 pruebas del backend y 135 de la interfaz. **No se ha probado** con la webcam real enfocando productos de verdad, ni desde un celular, ni con notificaciones reales de Yape (§4).

## 1. Cómo correrla

```bash
# 1. Una vez: galería y modelos en ml/data/models (ver docs/ml/reconocimiento.md)
# 2. Tu QR de Yape (Yape → «Mi QR» → guardar imagen) en privado/yape-qr.png (fuera de git)
chmod a+r privado/yape-qr.png
# 3. Levantar
docker compose -f docker-compose.yml -f docker-compose.demo.yml up --build
```

| Dirección | Para qué |
|---|---|
| http://localhost:5173 | El quiosco (lo que se vería en el celular). El navegador pide permiso para la cámara |
| http://localhost:5173/sim | Panel del presentador: la tarjeta **«Notificación de Yape»** simula el aviso de pago |
| http://localhost:5173/caja | Panel del cajero: ventas de hoy, ayudas |

El QR del comercio va en `privado/yape-qr.png` (fuera de git; `chmod a+r` para que el contenedor lo lea). Si falta, la API no arranca y el log dice dónde ponerlo.

## 2. Flujo

1. **INICIAR**. Se abre la cámara con un **recuadro amarillo**.
2. Pones un producto dentro del recuadro y lo mantienes quieto. La pantalla muestra su nombre con una barra que se llena y, cuando lo reconoce igual **3 veces seguidas** (~1,2 s), lo **agrega solo** y avisa «Agregado: …». Para el siguiente, saca el producto y pon otro. Para una segunda unidad del mismo, sácalo del recuadro y vuelve a meterlo. Si se equivoca, «−» quita uno.
3. **CONFIRMAR** → **PAGAR**. Aparece tu QR de Yape con el total.
4. La otra persona escanea el QR con su Yape o Plin y paga ese monto.
5. Llega la notificación de pago. En la demo se simula desde `/sim` con el texto «Juan Pérez te yapeó S/ 4.50». Si el monto coincide, la pantalla muestra **«Cobro exitoso»**, la boleta (número B001, fecha, quién pagó) y la lista. A los 10 s vuelve al inicio.

## 3. Reconocimiento con recuadro guía

- El navegador manda **solo el recuadro** (320×320 px, JPEG) cada 0,4 s a `POST /api/vision/frame`. El quiosco responde con el producto más parecido, su parecido y su **margen** sobre el segundo, sin cambiar la compra. La pantalla lo agrega cuando ve el mismo producto en 3 cuadros seguidos (`stepAutoAdd` en `kiosk-ui/src/kiosk/camara.ts`). No se guardan imágenes.
- **Por qué recuadro y no «cualquier fondo»:** el modelo que separa el producto de cualquier fondo (U²-Net «silueta») tarda **más de 1 s por imagen** en la laptop de desarrollo. Con el recuadro, cada imagen tarda **~100 ms**. El modo «fondo libre» sigue disponible con la cámara del servidor (`KIOSK_FONDO=libre`).
- **Galería del recuadro** (`python -m kiosk.recognizer galeria --recuadro` → `galeria-recuadro.npz`). Medido con las 107 fotos del Drive, consulta = recuadro central del 60 % y cada foto fuera de la galería:

  | Variante | Aciertos |
  |---|---|
  | Galería solo con el producto recortado (antes) | 77,6 % |
  | + recuadros centrales del 45/60/80 % de cada foto, color medido en el centro (peso 0,8) y promedio de las 2 huellas más parecidas de cada producto | **85,0 %** |
  | … y aceptando solo con parecido ≥ 1,2 y margen ≥ 0,05 | acepta 82 de 107, **acierta 79 (96 %)** |

  El margen evita confundir empaques parecidos (Casino y Cancún, los dos amarillos). Los errores que quedan son sobre todo entre empaques parecidos (Cancún/Chocman, Glacitas/Ritz).
- **Umbral y margen**: se guardan en la galería. Se cambian con `KIOSK_THRESHOLD` y `KIOSK_MARGIN`. El log muestra cada cambio, por ejemplo «Recuadro: CASINO-43 (mejor CASINO-43 1.38, margen 0.09)».
- **Lo que aún no se midió:** el acierto en vivo con la webcam de la demo. Las fotos del Drive se tomaron con celular sobre una mesa; la webcam ve otra luz y otro fondo. Mostrar el producto en la **pantalla de un celular** (una foto) en vez del producto real empeora el resultado: reflejos y el marco del teléfono.
- **Para que acierte más:** tomar fotos de cada producto con la misma cámara y luz de la demo (`capturar`, ver `docker-compose.camara.yml`) y regenerar la galería.

## 4. Pago con tu QR y la notificación

- El QR es el **estático** de tu Yape. El cliente escribe el monto en su app. Ese QR también se puede pagar desde Plin y las apps de bancos (QR interoperable).
- El pago se da por hecho cuando llega una **notificación** con el **monto exacto** del total mientras la pantalla espera. Endpoints:
  - `POST /sim/wallet-notification {"text": "..."}`: solo para la demo. Solo existe con `KIOSK_SIMULAR_PAGO=on` (apagado por defecto; `docker-compose.demo.yml` lo enciende).
  - `POST /api/pay/notification` con `Authorization: Bearer <KIOSK_NOTIFIER_KEY>`: para la futura app Android. Sin la clave responde 401.
- El intérprete (`parse_wallet_notification` en `kiosk-api/src/kiosk/payments.py`) toma el monto «S/ …» y, si lo encuentra, el nombre. **Los formatos son supuestos:** no se han visto notificaciones reales de Yape ni de Plin en este proyecto. Hay que confirmarlos con avisos reales antes de la app.
- **Riesgos conocidos:**
  - Un pago ajeno por el mismo monto, durante la espera, se tomaría como este. Mitigación posible: cobrar montos únicos (p. ej. S/ 4.51).
  - Leer notificaciones depende del texto que Yape decida mostrar. Si lo cambia, hay que actualizar el intérprete.
  - No hay confirmación de Yape ni de un banco: es una señal del celular del comercio, no un comprobante.

## 5. Camino a la app (pendiente)

| Pieza | Hoy (web) | En la app |
|---|---|---|
| Pantalla del quiosco | React en el navegador | React Native (se reutiliza la lógica y el diseño) |
| Cámara | `getUserMedia` + recuadro → `/api/vision/frame` | Cámara del celular + mismo recuadro → misma API, o el modelo en el celular |
| Reconocimiento | kiosk-api (Python, ONNX) en la laptop | kiosk-api en un servidor en la nube, o ONNX Runtime Mobile en el celular |
| Detección del pago | `/sim` simula la notificación | `NotificationListenerService` (Android) lee el aviso de Yape y llama a `/api/pay/notification` |
| Backend | kiosk-api local (SQLite) | kiosk-api desplegado (o Firebase para ventas y catálogo) |

Antes de la app conviene: probar con la webcam y productos reales, juntar ejemplos reales de notificaciones de Yape y Plin, y decidir dónde corre el reconocimiento (servidor o celular).
