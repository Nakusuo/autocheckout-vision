# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Clientes de una bodega de barrio o tienda pequeña (el primer caso estudiado fue una tienda de conveniencia en Av. Túpac Amaru, Comas, Lima) con una compra rápida de 1 a 3 productos, a menudo en hora punta (7–9 a. m., 12–2 p. m., 7–10 p. m.), que quieren pagar sin hacer la cola de la caja. Usan el quiosco de pie y sin instrucciones previas. El cajero interviene cuando el cliente pulsa SOLICITAR AYUDA y cuando el panel de caja muestra una alerta de seguridad automática (algo no reconocido pasó frente a la cámara).

## Product Purpose

Quiosco de autocobro: una cámara cenital reconoce los productos de la bandeja, una balanza confirma el peso (±5 g) y el cliente paga con un QR (Yape/Plin). Objetivos: cobro completo en ≤ 45 s, ninguna venta sin validación de peso y ≥ 80 % de compras completadas sin ayuda.

## Positioning

El cliente no escanea nada: deja los productos en la bandeja y la visión más el peso hacen el trabajo.

## Operating Context

- Flujo fijo: W1 Inicio → W2 Escaneo → W3 Confirmar → QR de pago → W4 Boleta (completa, con IMPRIMIR BOLETA y NUEVA COMPRA) → vuelta a W1 a los 30 s o al tocar NUEVA COMPRA. Además, la pantalla Fuera de servicio.
- El pago espera hasta 120 s. Si el peso no coincide, se muestra «Revise su bandeja» y PAGAR queda bloqueado.
- SOLICITAR AYUDA siempre visible; avisa al panel de caja.
- MVP de un equipo universitario: hardware simulado (balanza, pantalla táctil, pasarela). La demo se muestra en una laptop horizontal con el quiosco 9:16 centrado.

## Capabilities and Constraints

- Interfaz vertical 9:16 pensada para 1080×1920 (RNF-06), React + Vite.
- Textos obligatorios del SRS: «[AUTO-CHECKOUT] Coloca tus productos», INICIAR, CORREGIR, PAGAR, SOLICITAR AYUDA, «Revise su bandeja».
- Montos en soles: `S/ 0.00`.
- Las pruebas e2e localizan elementos por esos textos y roles; cambiarlos rompe las pruebas.

## Brand Commitments

- Nombre visible del sistema: **Caserito** (2026-11-22; «caserito» es como la bodega llama a su cliente de siempre). Cada bodega pone su nombre en la boleta con `KIOSK_TIENDA`. El repositorio y los documentos técnicos siguen llamándose AutoCaja / autocheckout-vision. No se usa el nombre ni el logo de OXXO ni de otra tienda sin autorización.
- Paleta (2026-11-23, revisada con ui-ux-pro-max y las reglas anti AI-slop del usuario): papel y tinta cálidos con **un solo acento rojo #C8372A**; verde #2F6B45 solo para «salió bien» y amarillo #E3A72F solo para precaución (ver DESIGN.md). Parte de la paleta de referencia que eligió el usuario el 2026-11-22.
- Tono: cercano y de barrio, de «tú», sin perder los textos obligatorios del SRS.

## Evidence on Hand

- Catálogo real de 11 productos en `catalog/products.csv` (nombre, precio, peso). No hay fotos de producto para la interfaz ni testimonios o métricas de uso todavía; no se inventan.

## Product Principles

1. Un paso, una decisión: cada pantalla pide una sola acción clara.
2. El estado del sistema siempre a la vista: qué se reconoció, si el peso coincide, cuánto falta para pagar.
3. Nadie se queda atascado: la ayuda está a un toque en todas las pantallas.
4. Rápido de leer de pie y a distancia de brazo.

## Accessibility & Inclusion

Uso público y táctil: blancos táctiles grandes, contraste alto (WCAG AA como mínimo) y estados que no dependan solo del color.
