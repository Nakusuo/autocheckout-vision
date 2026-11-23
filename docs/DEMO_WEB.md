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
| http://localhost:5173/ayuda | Vista del encargado: solicitudes de ayuda y alertas de seguridad |

El QR del comercio va en `privado/yape-qr.png` (fuera de git; `chmod a+r` para que el contenedor lo lea). Si falta, la API no arranca y el log dice dónde ponerlo.

## 2. Flujo

1. **INICIAR**. Se abre la cámara con un **recuadro amarillo**.
2. Pones un producto dentro del recuadro y lo mantienes quieto. La pantalla muestra su nombre con una barra que se llena y, cuando lo reconoce igual **3 veces seguidas** (~1,2 s), lo **agrega solo** y avisa «Agregado: …». Para el siguiente, saca el producto y pon otro. Para una segunda unidad del mismo, sácalo del recuadro y vuelve a meterlo. Si se equivoca, «−» quita uno.
3. **CONFIRMAR** → **PAGAR**. Aparece tu QR de Yape con el total.
4. La otra persona escanea el QR con su Yape o Plin y paga ese monto.
5. Llega la notificación de pago al celular del comercio. **La reenvía al quiosco MacroDroid** (§4.1) mientras no exista la app Android; sin eso, la pantalla espera hasta que vence el tiempo o hasta que la caja pulsa «Aprobar pago» en `/ayuda`. Cuando llegue la notificación con el monto exacto, la pantalla muestra **«Cobro exitoso»**, la boleta (número B001, fecha, quién pagó) y la lista. A los 10 s vuelve al inicio.

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
  - `POST /sim/wallet-notification {"text": "..."}`: **simulación** para pruebas automáticas, sin pantalla. Solo existe con `KIOSK_SIMULAR_PAGO=on` (apagado por defecto, también en la demo).
  - `POST /api/pay/notification` con `Authorization: Bearer <KIOSK_NOTIFIER_KEY>`: para la futura app Android. Sin la clave responde 401.
- El intérprete (`parse_wallet_notification` en `kiosk-api/src/kiosk/payments.py`) toma el monto «S/ …» y, si los encuentra, el nombre y el código de seguridad. **Formato de Yape verificado con una notificación real** (2026-11-20): título «Confirmación de Pago» y texto «Alessandra Rod\* te envió un pago por S/ 1.5. El cód. de seguridad es: 305» (el monto puede venir sin el cero final). Otra variante real: «Yape! NOMBRE APELLIDOS te envió un pago por S/ 1.50», sin código. Plin y otras variantes de Yape siguen sin verificar.
- Si llega un Yape que **no calza** (no hay compra esperando o el monto es distinto), la caja ve una alerta en `/ayuda` con el nombre, el monto y el código, para devolverlo o cobrarlo a mano. No se descarta sola.
- **Caja (`/ayuda`)**: muestra las **ventas de hoy** con el detalle (productos, total, hora, quién pagó y cómo: «Yape (notificación)», «Aprobado en caja» o «Simulado»). Mientras el cliente está en la pantalla de pago aparece **«Aprobar pago»**: es el respaldo si el encargado ve el Yape en su celular y la notificación no llegó (la boleta queda con `charge_id` «caja-billetera-…»).

- **QR con el monto incluido: probado y descartado** (2026-11-23). El QR de Yape del comercio sigue el estándar EMV del BCRP, que admite el monto (etiqueta 54). Se generó un QR con la misma cuenta, monto S/ 0.10 y tipo dinámico (01=12), con su código de control correcto: Yape lo abrió pero **ignoró el monto** y pidió escribirlo. Con una cuenta personal no se puede fijar el monto; eso lo dan los QR de comercio (Izipay, Niubiz, Culqi, Yape para negocios), que piden RUC y contrato. Decisión del equipo: seguir con el QR fijo, la indicación «Escribe exactamente S/ …» y la alerta en caja si el monto no calza.

### 4.1 Reenviar la notificación con MacroDroid (sin programar)

Mientras no exista la app Android, la app gratuita **MacroDroid** (Play Store) hace lo mismo en el celular que recibe los Yape:

1. MacroDroid → **Agregar macro**.
2. **Disparador**: *Notificación* → *Notificación recibida* → aplicación **Yape** → contenido que contenga `te envió un pago`.
3. **Acción**: *Web* → **Solicitud HTTP**:
   - Método `POST`, URL `https://<tu-túnel>.trycloudflare.com/api/pay/notification` (con el plan B la dirección cambia en cada arranque: hay que actualizarla).
   - Cabecera `Authorization` = `Bearer <KIOSK_NOTIFIER_KEY>` (está en `.env`).
   - Cuerpo, tipo `application/json`: `{"text": "[notification]"}`. Se usa solo el texto de la notificación (sin el título) para que el nombre se lea bien.
4. Dar a MacroDroid el permiso de **acceso a notificaciones** y quitarle el **ahorro de batería**.
5. Probar: una compra, pagar el monto exacto y ver que la pantalla pasa a «Cobro exitoso» y la venta aparece en `/ayuda`.

**Qué se probó**: el 2026-11-20 se envió el texto real a `/api/pay/notification` y se interpretó bien (S/ 1.50, «Alessandra Rod\*», código 305). El **2026-11-22 se probó de punta a punta**: compra de S/ 1.50 en el quiosco por el túnel, pago real con Yape, MacroDroid reenvió la notificación y el quiosco emitió la boleta solo, sin aprobar en caja.

Lo que se aprendió al configurarlo:
- MacroDroid **no mandaba la cabecera `Authorization`**: la clave va en el cuerpo, `{"text": "[notification]", "key": "<KIOSK_NOTIFIER_KEY>"}` (la cabecera sigue aceptándose).
- El texto de la notificación puede romper el JSON (saltos de línea, comillas): la API lo lee de forma tolerante (`parse_notifier_body`) y, si no encuentra el texto, lo registra con la clave tapada.
- El **túnel rápido de Cloudflare se cae cada pocas horas** («Tunnel not found») y al reiniciarlo cambia la dirección: hay que actualizar la URL en MacroDroid. Para algo estable hace falta un túnel con nombre fijo o enviar el aviso por la red local.
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
| Detección del pago | MacroDroid reenvía la notificación (§4.1); respaldo: «Aprobar pago» en `/ayuda` | `NotificationListenerService` (Android) lee el aviso de Yape y llama a `/api/pay/notification` |
| Backend | kiosk-api local (SQLite) | kiosk-api desplegado (o Firebase para ventas y catálogo) |

Antes de la app conviene: probar con la webcam y productos reales, juntar ejemplos reales de notificaciones de Yape y Plin, y decidir dónde corre el reconocimiento (servidor o celular).
