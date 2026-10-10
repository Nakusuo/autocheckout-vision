---
name: AutoCaja
description: Quiosco de autocobro que se lee como señalética vial, en rojo, amarillo y blanco.
colors:
  sign-red: "#c8102e"
  sign-red-press: "#9e0c24"
  sign-yellow: "#ffc72c"
  sign-yellow-soft: "#fff3cc"
  sign-white: "#ffffff"
  ink: "#141414"
  ink-soft: "#4a4a4a"
  rule: "#d9d6cf"
  disabled-bg: "#e6e3dc"
  disabled-ink: "#5c5a55"
  asphalt: "#2a2a2a"
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
    backgroundColor: "{colors.sign-red}"
    textColor: "{colors.sign-white}"
    typography: "{typography.action}"
    rounded: "{rounded.plate}"
    height: "15cqw"
  button-go-hover:
    backgroundColor: "{colors.sign-red-press}"
  button-plain:
    backgroundColor: "{colors.sign-white}"
    textColor: "{colors.ink}"
    typography: "{typography.action}"
    rounded: "{rounded.plate}"
    height: "15cqw"
  button-help:
    backgroundColor: "{colors.sign-white}"
    textColor: "{colors.ink}"
    rounded: "{rounded.plate}"
    height: "11cqw"
  button-disabled:
    backgroundColor: "{colors.disabled-bg}"
    textColor: "{colors.disabled-ink}"
  total-band:
    backgroundColor: "{colors.sign-yellow}"
    textColor: "{colors.ink}"
    padding: "4cqw"
  alert:
    backgroundColor: "{colors.sign-yellow-soft}"
    textColor: "{colors.ink}"
    rounded: "{rounded.plate}"
  qty-badge:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.sign-white}"
    rounded: "{rounded.badge}"
    size: "8cqw"
---

# Design System: AutoCaja

## Overview

**Creative North Star: "La placa de carretera"**

Cada estado del quiosco es una placa de señalización completa que se entiende de un vistazo, de pie y a la distancia de un brazo. El sistema toma su gramática de la señalética vial peruana: placas blancas con borde, discos numerados para la ruta, rombos amarillos para la precaución, el octógono rojo para el bloqueo total y la señal de velocidad para cada cuenta regresiva. Los colores son los de la tienda (rojo, amarillo y blanco), pero cada uno tiene un trabajo fijo.

La pantalla es densa solo donde hace falta (la lista de productos) y el resto es aire y una acción. No se usa el nombre ni el logo de OXXO: la marca visible es AutoCaja.

**Key Characteristics:**
- Una placa por estado, que entra con un salto seco de arriba abajo.
- El rojo solo aparece donde se puede pulsar o donde algo se detiene.
- El amarillo significa precaución o el monto a pagar; nunca decora.
- Bordes de tinta gruesos, sin sombras dentro de la placa.
- Todo se escala con el ancho del quiosco (`cqw`), así que se ve igual a 1080×1920 que centrado en una laptop.

## Colors

Tres colores de señal sobre tinta casi negra, cada uno con un significado fijo.

- **Rojo señal (`sign-red`)**: la acción principal (INICIAR, CONFIRMAR, PAGAR), el paso actual de la ruta, la palabra «Caja» del nombre, el aro de la señal de velocidad y el octógono de PARE. Al pasar el cursor o pulsar se usa `sign-red-press`.
- **Amarillo señal (`sign-yellow`)**: los rombos de precaución, la franja bajo la cabecera, la banda del TOTAL y el aviso «Reconectando…». `sign-yellow-soft` es el fondo de las alertas, para que el texto negro largo se lea sin fatiga.
- **Blanco placa (`sign-white`)**: la superficie de todo el quiosco.
- **Tinta (`ink`, `ink-soft`)**: el texto, los bordes de placa, la insignia de cantidad y los pasos ya hechos. `ink-soft` es el texto secundario (8.9:1 sobre blanco).
- **Asfalto (`asphalt`)**: solo alrededor del quiosco cuando se ve en una pantalla horizontal. Las vistas internas `/sim` y `/caja` no lo usan.

Los estados nunca dependen solo del color: el peso correcto lleva el disco con el visto bueno; el que no coincide, el rombo y la diferencia en gramos; lo deshabilitado cambia también el borde.

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

Plano: la profundidad la dan los bordes de tinta, no las sombras. La única sombra es la del quiosco entero sobre el asfalto. La franja amarilla con su filo negro separa la cabecera del contenido.

## Shapes

- Placas y botones con radio `2cqw`; la placa del QR, una vez y media ese radio.
- Borde de placa de `0.7cqw` en tinta; el QR lleva `1cqw`.
- Los botones de acción llevan el borde interior blanco de las señales (dos `inset box-shadow`).
- Formas de señal dibujadas como geometría SVG en `src/kiosk/signs.tsx`: rombo, octógono, disco de visto bueno, flecha, signo de ayuda y la bandeja con productos. Todas son `aria-hidden`; el texto lleva el significado.

## Components

- **Ruta**: cuatro discos (Coloca, Confirma, Paga, Listo). El paso actual va en rojo, los hechos en tinta y los pendientes con aro. El número sale de `data-n` por CSS para no repetir cifras en el texto de la pantalla.
- **Botón go**: placa roja de `15cqw` de alto con borde interior blanco y flecha. Al pulsar se encoge al 98 %. El foco es un anillo amarillo con filo negro.
- **Botón plain**: placa blanca con borde de tinta (CORREGIR).
- **Botón de ayuda**: placa blanca más baja, siempre al pie. Encima, «Ayuda en camino» en una banda de tinta.
- **Tablero**: lista con la cantidad en una insignia negra, el nombre y el precio a la derecha, y la banda amarilla del TOTAL.
- **Alerta**: placa amarilla clara con borde de tinta y rombo de precaución.
- **Señal de velocidad**: disco blanco con aro rojo y la cifra en negro para los 120 s del pago y los 10 s del ticket.
- **Fuera de servicio**: octógono rojo de PARE sobre el título.

- **Escaneo en vivo** (W2): una píldora «En vivo» junto al título (punto rojo que late). Cada producto nuevo se marca «+ Agregado» (fila amarilla clara y etiqueta roja) unos 2,4 s. Una pista invita a pulsar CONFIRMAR cuando estén todos: el cliente decide cuándo termina.
- **Escanear de nuevo** (W2): placa blanca más baja, debajo de CONFIRMAR. Abre una ventana visible de 4 s: la píldora pasa a roja con la cuenta («De nuevo… 3 s»), una barra roja avanza por el borde superior del tablero, las líneas reaparecen una tras otra y CONFIRMAR queda bloqueado hasta el final. En W3, una pista indica que CORREGIR permite seguir escaneando.
- **Aviso de cámara** (W1 y W2): una línea pequeña con el ícono de cámara y la Ley 29733.

**Paneles del equipo (`/sim`, `/caja`)**: misma paleta, tipografía y placas, pero a escala de escritorio (`rem`) y en dos columnas: tarjetas blancas con borde de tinta sobre fondo `#f3f1ec`, botones `pbtn` (rojo = acción principal) y el estado del quiosco como disco rojo con el código de pantalla. Estilos en `kiosk-ui/src/panels/panels.css`.

Movimiento: la placa entra en 260 ms (clip de arriba abajo y un desplazamiento de 2cqw, curva de salida exponencial); las líneas nuevas entran desde la izquierda; la línea roja recorre la bandeja mientras se escanea. Con `prefers-reduced-motion` todo queda quieto.

## Do's and Don'ts

- **Do** reservar el rojo para acciones y bloqueos, y el amarillo para precaución y el monto a pagar.
- **Do** acompañar cada estado con forma y texto, no solo con color.
- **Do** mantener los textos del SRS exactos; las pruebas los usan.
- **Don't** usar el nombre ni el logo de OXXO sin autorización.
- **Don't** añadir sombras, degradados o tarjetas dentro de la placa; la profundidad es el borde de tinta.
- **Don't** poner etiquetas pequeñas encima de los títulos.
