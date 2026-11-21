---
title: AutoCaja
emoji: 🛒
colorFrom: red
colorTo: yellow
sdk: docker
app_port: 7860
pinned: false
---

# AutoCaja: quiosco de autocobro con visión (demo)

Proyecto académico. Pon un producto frente a la cámara dentro del recuadro amarillo; se agrega solo
cuando se reconoce. El pago es con el QR de Yape del comercio y se confirma con la notificación
de pago que envía la app Android del comercio (**en desarrollo**: sin ella el pago no se completa).

- `/` pantalla del cliente · `/ayuda` vista de la caja (pide clave).
- Código, pruebas y documentación: repositorio de GitHub del proyecto.
- Datos de ventas: se pierden cuando el Space se reinicia (plan gratis, sin disco persistente).
