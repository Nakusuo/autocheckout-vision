---
version: 1
slug: "kiosk-ui-src-kiosk-kiosk-tsx"
primary_target: "kiosk-ui/src/kiosk/Kiosk.tsx"
related_targets: ["kiosk-ui/src/tokens.css"]
---

# Quiosco del cliente (kiosk-ui, W1–W4)

Modo: Operate. Cliente de pie, compra de 1 a 3 productos, sin instrucciones. Una acción por pantalla; estado siempre visible; ayuda a un toque. Restricciones: textos y roles del SRS (las e2e los usan), 9:16 centrado en laptop horizontal, paleta roja, amarilla y blanca, nombre AutoCaja sin marca OXXO.

## Direction contract

THESIS: El quiosco se lee como señalética vial: cada estado es una placa completa que se entiende de un vistazo. Rechaza el «app de tarjetas con barra de color arriba».
OWN-WORLD: Placa blanca con borde interior, disco rojo con número para los pasos, rombo amarillo con borde negro para precaución, octógono rojo para el bloqueo total, señal de velocidad (aro rojo, cifra negra) para cada cuenta regresiva. Rótulo Overpass (heredera de Highway Gothic), mayúsculas en acciones. El rojo es solo para lo que se puede pulsar o lo que detiene.
STORY: El cliente sigue la ruta 1-2-3-4, ve qué reconoció la cámara, sabe si el peso coincide y paga.
FIRST VIEWPORT: Cabecera blanca con AutoCaja y los cuatro discos de ruta; en W1, un rombo amarillo grande con la bandeja y el título en dos líneas; INICIAR como placa roja a todo el ancho en el tercio inferior; SOLICITAR AYUDA como placa blanca al pie.
FORM: señalética vial peruana, puesto 7 de 7, seed 325701ca. Raises: un estado ocupa toda la placa y cambia con un salto seco (del feed vertical); el color de acción solo vive donde se puede actuar (de la app cálida de consumo).
FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
