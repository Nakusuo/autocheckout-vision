---
name: Caserito
description: Autocobro para la bodega del barrio, cálido y claro, en chili, azafrán, hoja y crema.
colors:
  chili: "#d23d2d"
  chili-press: "#a62e21"
  saffron: "#f5c065"
  saffron-soft: "#fbe6b8"
  leaf: "#31603d"
  leaf-soft: "#dde9d8"
  paper: "#f8eecb"
  paper-light: "#fffcf2"
  ink: "#3a2622"
  ink-soft: "#6e433d"
  rule: "#e2d0a2"
  disabled-bg: "#ebe1c4"
  disabled-ink: "#6b5850"
  counter: "#2e1e1b"
typography:
  display:
    fontFamily: "Overpass, Segoe UI, system-ui, sans-serif"
    fontSize: "8.8cqw"
    fontWeight: 900
    lineHeight: 1.05
    letterSpacing: "-0.02em"
  headline:
    fontFamily: "Overpass, Segoe UI, system-ui, sans-serif"
    fontSize: "8cqw"
    fontWeight: 900
    lineHeight: 1.05
    letterSpacing: "-0.02em"
  amount:
    fontFamily: "Overpass, Segoe UI, system-ui, sans-serif"
    fontSize: "14cqw"
    fontWeight: 900
    lineHeight: 1
    letterSpacing: "-0.03em"
    fontFeature: "tnum"
  body:
    fontFamily: "Overpass, Segoe UI, system-ui, sans-serif"
    fontSize: "4.2cqw"
    fontWeight: 600
    lineHeight: 1.35
  action:
    fontFamily: "Overpass, Segoe UI, system-ui, sans-serif"
    fontSize: "5.6cqw"
    fontWeight: 900
    letterSpacing: "0.06em"
  label:
    fontFamily: "Overpass, Segoe UI, system-ui, sans-serif"
    fontSize: "2.4cqw"
    fontWeight: 800
    letterSpacing: "0.04em"
rounded:
  plate: "2cqw"
  badge: "1.2cqw"
  disc: "50%"
spacing:
  gutter: "5cqw"
  stack: "3.2cqw"
  tight: "2.4cqw"
components:
  button-go:
    backgroundColor: "{colors.chili}"
    textColor: "{colors.paper-light}"
    typography: "{typography.action}"
    rounded: "{rounded.plate}"
    height: "15cqw"
  button-go-hover:
    backgroundColor: "{colors.chili-press}"
  button-plain:
    backgroundColor: "{colors.paper-light}"
    textColor: "{colors.ink}"
    typography: "{typography.action}"
    rounded: "{rounded.plate}"
    height: "15cqw"
  button-help:
    backgroundColor: "{colors.paper-light}"
    textColor: "{colors.ink}"
    rounded: "{rounded.plate}"
    height: "11cqw"
  button-disabled:
    backgroundColor: "{colors.disabled-bg}"
    textColor: "{colors.disabled-ink}"
  total-band:
    backgroundColor: "{colors.saffron}"
    textColor: "{colors.ink}"
    padding: "4cqw"
  alert:
    backgroundColor: "{colors.saffron-soft}"
    textColor: "{colors.ink}"
    rounded: "{rounded.plate}"
  qty-badge:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.paper-light}"
    rounded: "{rounded.badge}"
    size: "8cqw"
---

# Design System: Caserito

## Overview

**Creative North Star: "El mostrador de la bodega de confianza"**

Cada estado es una tarjeta clara que se entiende de un vistazo, de pie y a la distancia de un brazo, con el trato cercano de la bodega del barrio: se le habla de tú al cliente y al final recibe su boleta como en el mostrador. De la etapa anterior se conservan las formas útiles de la señalética (discos numerados de la ruta, rombo de precaución, PARE para el bloqueo total), ahora en la paleta cálida de bodega.

La pantalla es densa solo donde hace falta (la lista de productos) y el resto es aire y una acción. No se usa el nombre ni el logo de OXXO: la marca visible es Caserito.

**Key Characteristics:**
- Una placa por estado, que entra con un salto seco de arriba abajo.
- El rojo solo aparece donde se puede pulsar o donde algo se detiene.
- El amarillo significa precaución o el monto a pagar; nunca decora.
- Bordes de tinta gruesos, sin sombras dentro de la placa.
- Todo se mide en `--u` (en este documento, «cqw»): 1/100 del ancho de la placa vertical. En el quiosco (1080×1920) y en el celular, `--u` sale del ancho y la placa ocupa toda la pantalla. En una pantalla horizontal (laptop), `--u` sale del alto y el ancho que sobra se usa: la cámara a la izquierda y la lista a la derecha al escanear, el QR junto a los pasos al pagar, y la lista junto a las acciones al confirmar.
- En celular los textos más chicos tienen un mínimo legible (11-12 px) y SOLICITAR AYUDA queda fija al pie si hay que desplazarse.

## Colors

Paleta de bodega elegida por el usuario (2026-11-22): rojo chili, crema vainilla, azafrán, verde hoja y marrón. Cada color tiene un trabajo fijo.

- **Chili (`chili`)**: la acción principal (INICIAR, CONFIRMAR, PAGAR, IMPRIMIR BOLETA), el paso actual de la ruta, el nombre del sistema y de la tienda en la boleta, y lo que detiene (PARE). Al pulsar, `chili-press`.
- **Azafrán (`saffron`)**: lo que hay que mirar: la banda del TOTAL, la franja bajo la cabecera, los rombos de precaución. `saffron-soft` es el fondo de las alertas y el «hover» de los botones claros.
- **Hoja (`leaf`)**: salió bien: pasos hechos, producto agregado, peso correcto, «Cobro exitoso» y el visto bueno.
- **Crema (`paper`)** es la superficie del quiosco y de `/ayuda`; **papel (`paper-light`)** son las tarjetas, la boleta, los botones claros y el fondo del QR.
- **Tinta (`ink`, `ink-soft`)**: marrón oscuro para el texto y los bordes; `ink-soft` (7:1 sobre crema) para lo secundario.
- **Mostrador (`counter`)**: el fondo alrededor de la placa en pantallas verticales anchas.

Contraste medido: texto crema sobre chili 5,5:1, tinta suave sobre crema 7,1:1, tinta suave sobre azafrán 5:1, crema sobre hoja 6,3:1. Los estados nunca dependen solo del color: el peso correcto lleva el disco con el visto bueno; el que no coincide, el rombo y la diferencia en gramos.

## Typography

Una sola familia: **Overpass** (heredera de Highway Gothic, la letra de las señales de carretera), empaquetada con `@fontsource/overpass` en los pesos 600, 800 y 900, para que funcione sin internet. Las cifras son tabulares en todo el quiosco.

- **Display / headline (900, −0.02em)**: los títulos de cada pantalla, con `text-wrap: balance`. «[AUTO-CHECKOUT]» no se parte en el guion (`.nowrap`).
- **Amount (900, 14cqw)**: el monto en la pantalla del QR; el TOTAL del tablero va a 8.5cqw.
- **Action (900, mayúsculas, +0.06em)**: el texto de los botones, igual que los textos del SRS (INICIAR, PAGAR…).
- **Body (600, 4.2cqw)**: indicaciones de una o dos líneas, máximo 36ch.
- **Label (800, mayúsculas)**: las etiquetas de la ruta y «Total a pagar».

## Layout

Columna única en 9:16: cabecera (nombre y ruta), placa del estado (flexible) y ayuda al pie. Margen lateral `5cqw`, separación vertical `3.2cqw`. El tablero de productos toma la altura de su contenido y lo que sigue se apoya en la parte inferior, donde está la mano. En una pantalla horizontal el quiosco se centra a toda la altura sobre el asfalto.

## Elevation & Depth

Plano: la profundidad la dan los bordes de tinta, no las sombras. Sombras solo con función: la del quiosco sobre el mostrador, la de la boleta (papel sobre la placa) y el canto inferior del botón principal, que se hunde al tocarlo. La franja azafrán separa la cabecera del contenido.

## Shapes

- Placas y botones con radio `3cqw` (más amable que el de señal vial); la placa del QR, una vez y media ese radio.
- Borde de placa de `0.7cqw` en tinta; el QR lleva `1cqw`.
- El botón principal tiene un canto de `chili-press` debajo y baja `0.8cqw` al pulsarlo.
- Formas de señal dibujadas como geometría SVG en `src/kiosk/signs.tsx`: rombo, octógono, disco de visto bueno, flecha, signo de ayuda y la bandeja con productos. Todas son `aria-hidden`; el texto lleva el significado.

## Components

- **Ruta**: cuatro discos (Coloca, Confirma, Paga, Listo). El paso actual va en chili, los hechos en hoja y los pendientes con aro. El número sale de `data-n` por CSS para no repetir cifras en el texto de la pantalla.
- **Botón go**: placa chili de `15cqw` de alto con canto inferior y flecha (o ícono). El foco es un anillo azafrán con filo de tinta.
- **Botón plain**: placa de papel con borde de tinta (CORREGIR, NUEVA COMPRA).
- **Botón de ayuda**: placa blanca más baja, siempre al pie. Encima, «Ayuda en camino» en una banda de tinta.
- **Tablero**: lista con la cantidad en una insignia negra, el nombre y el precio a la derecha, y la banda amarilla del TOTAL.
- **Alerta**: placa amarilla clara con borde de tinta y rombo de precaución.
- **Señal de velocidad**: disco de papel con aro chili y la cifra en tinta para los 120 s del pago.
- **Boleta** (W4): papel de ticketera con el nombre de la tienda (`KIOSK_TIENDA`, o «Caserito»), número, fecha, productos con cantidad, precio unitario e importe, la banda azafrán del total, cómo se pagó y quién pagó, y al pie «Boleta simulada, sin validez ante SUNAT». Queda 30 s; al lado, IMPRIMIR BOLETA (impresión del navegador; la hoja de impresión deja solo la boleta, en negro, a 80 mm) y NUEVA COMPRA.
- **Fuera de servicio**: octógono rojo de PARE sobre el título.

- **Escaneo en vivo, uno por uno** (W2): la píldora «En vivo» (punto rojo que late) junto al título. El cliente pasa cada producto frente a la cámara y se suma a la lista: la fila nueva se pone amarilla clara, la insignia de cantidad roja y la etiqueta «+ Agregado» flota en el margen superior (no cambia la altura). Cada línea tiene un botón cuadrado «−» para quitar una unidad. Mientras el producto llega a la bandeja se ve «Pesando la bandeja…» (aro que gira) y CONFIRMAR espera; «Revise su bandeja» solo aparece si la diferencia dura más de 2 s.
- **Inicio, «cómo funciona»** (W1): una demostración en bucle de 5 s (`DemoVisor` en `signs.tsx`): un paquete entra a la pantalla de la cámara, una línea lo recorre, las esquinas se ponen verdes y aparece su etiqueta con nombre y precio. Debajo, tres pasos numerados en discos verdes. Con movimiento reducido se ve el final, quieto.
- **Visor de la cámara** (W2 con cámara del navegador): cuatro esquinas en lugar de un marco y la imagen oscurecida fuera del visor. Buscando: una línea azafrán lo recorre. Reconociendo: las esquinas se vuelven claras y se cierran hacia el producto a medida que se confirma (`--p`, 3 cuadros) y bajo el visor flota una etiqueta con el nombre y el precio. Agregado: el visor se tiñe de verde con el visto bueno. No se muestra un porcentaje de seguridad porque el reconocedor no da uno real. Todo el visor es decorativo (`aria-hidden`); el texto accesible va en `role=status`.
- **Cancelar compra** (W2, W3 y QR): la acción más callada, texto subrayado sin placa, debajo de la acción principal. Vuelve al inicio y descarta la lista.
- **Aviso de cámara** (W1 y W2): una línea pequeña con el ícono de cámara y la Ley 29733.

**Vista de ayuda (`/ayuda`)**: misma paleta, tipografía y placas, pero a escala de escritorio (`rem`) y en una columna: tarjetas de papel con borde de tinta sobre fondo crema, las ventas de hoy con su detalle y «Aprobar pago» mientras el cliente paga, botones `pbtn` (rojo = acción principal) y el estado del quiosco como disco rojo con el código de pantalla. Estilos en `kiosk-ui/src/panels/panels.css`.

Movimiento: la placa entra en 260 ms (clip de arriba abajo y un desplazamiento de 2cqw, curva de salida exponencial); las líneas nuevas entran desde la izquierda; la línea roja recorre la bandeja mientras se escanea. Con `prefers-reduced-motion` todo queda quieto.

## Do's and Don'ts

- **Do** reservar el chili para acciones y bloqueos, el azafrán para el total y la precaución, y el verde hoja para lo que salió bien.
- **Do** acompañar cada estado con forma y texto, no solo con color.
- **Do** mantener los textos del SRS exactos; las pruebas los usan.
- **Don't** usar el nombre ni el logo de OXXO sin autorización.
- **Don't** añadir degradados ni sombras de adorno; las únicas sombras son las de la lista de Elevation.
- **Don't** poner etiquetas pequeñas encima de los títulos.
