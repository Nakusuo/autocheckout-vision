# Especificación de Requisitos de Software (SRS)
## Sistema de Cobro Automatizado por Reconocimiento Visual (OXXO)

> Documento original recibido por el equipo. Las decisiones que lo ajustan están en
> `docs/superpowers/specs/2026-10-03-autocheckout-design.md`.

---

## 1 INTRODUCCIÓN

### 1.1 Alcance
El presente documento especifica los requisitos de software para el MVP (Producto Mínimo Viable) del Sistema de Cobro Automatizado por Visión Computacional, a implementarse como canal de auto-atención (Auto-Checkout) en la tienda OXXO sede Av. Túpac Amaru, Comas. El sistema comprende una interfaz táctil, un motor de inferencia de Inteligencia Artificial (Edge Computing) conectado a una cámara cenital RGB para reconocimiento multiobjeto, integración con una celda de carga (balanza IoT) para validación de peso, y un módulo de pago digital para billeteras móviles. El alcance de esta fase se limita a transacciones rápidas de 1 a 3 productos (camino feliz).

### 1.2 Objetivos
*   **Agilizar el proceso de cobro:** Reducir el tiempo de transacción de las compras rápidas a un máximo de 45 segundos.
*   **Reducir la fricción operativa:** Disminuir las colas en horas punta delegando transacciones menores al quiosco autónomo.
*   **Asegurar la integridad de la venta:** Prevenir mermas y hurtos mediante un sistema de validación redundante (peso y visión).

---

## 2 INFORMACIÓN DEL DOMINIO DEL PROBLEMA

### 2.1 Introducción al Dominio del Problema
Actualmente, el proceso de cobro en OXXO Lima Norte depende de un único cajero que escanea manualmente cada ítem en el POS. Esto genera cuellos de botella en horas de alta afluencia (7-9 a.m., 12-2 p.m. y 7-10 p.m.). Los clientes sufren tiempos de espera de hasta 8 minutos, lo que resulta en frustración y abandono de la compra. Las soluciones convencionales trasladan el trabajo de escaneo al cliente, pero no resuelven la lentitud de pasar código por código.

### 2.2 Glosario de Términos
*   **Visión Computacional / YOLOv8:** Algoritmo de Inteligencia Artificial para detectar múltiples productos simultáneamente.
*   **Edge Computing:** Procesamiento de datos de forma local (en la misma terminal), garantizando baja latencia y funcionamiento sin internet.
*   **Celda de Carga:** Sensor electrónico (balanza IoT) que mide el peso físico de los artículos.
*   **Fusión Sensorial:** Proceso lógico que cruza los datos visuales de la cámara con el peso de la bandeja.
*   **Camino Feliz (Happy Path):** El flujo ideal donde el cliente escanea, pesa y paga sin ningún error (Vistas W1 a W4).

---

## 3 NECESIDADES DE NEGOCIO

### 3.1 Objetivos de Negocio a Implantar

| ID | Objetivo de Negocio | Descripción | Métrica de Éxito |
| :--- | :--- | :--- | :--- |
| **ON-01** | Reducción de tiempo de cobro | Reducir el tiempo promedio de atención para compras express (1 a 3 artículos). | Tiempo total ≤ 45 segundos. |
| **ON-02** | Control automatizado de mermas | Validar todas las transacciones mediante peso físico antes de habilitar el pago. | Margen de error ≤ 5 gramos. |
| **ON-03** | Adopción de autoservicio | Lograr que los clientes puedan completar el flujo sin solicitar asistencia humana. | Tasa de éxito autónomo ≥ 80%. |

### 3.2 Descripción de los Actores del Sistema

| Actor | Descripción | Responsabilidades en el Sistema |
| :--- | :--- | :--- |
| **Cliente** | Usuario final en tienda. | Inicia transacción, coloca productos, confirma la lista y paga. |
| **Cajero (Roxana)** | Personal operativo de OXXO. | Acude a resolver bloqueos físicos o errores en la terminal (ayuda). |
| **Sistema POS** | Sistema de ventas de OXXO. | Emite la boleta fiscal electrónica y descuenta el stock (Integración). |

### 3.3 Casos de Uso del Sistema (MVP)

| ID | Nombre del Caso de Uso | Actor Principal | Descripción del Flujo |
| :--- | :--- | :--- | :--- |
| **CU-01** | Identificación Visual | Cliente | Coloca ítems en bandeja. La cámara toma captura, procesa con IA y lista los productos en pantalla con su precio y peso teórico. |
| **CU-02** | Validación de Peso | Sistema | Lee la balanza. Si el peso real coincide con el teórico (± 5g), habilita el cobro. Si difiere, bloquea y muestra error. |
| **CU-03** | Pago mediante Código QR | Cliente | Selecciona "Pagar". El sistema genera QR (Yape/Plin). El usuario escanea y paga. El sistema verifica el webhook y cierra la venta. |

---

## 3.4 Requisitos Funcionales del Sistema

**3.4.1 RECONOCIMIENTO VISUAL (MOTOR IA)**
*   **3.4.1.1** La aplicación deberá capturar video en tiempo real desde la cámara cenital instalada sobre la bandeja.
*   **3.4.1.2** La aplicación deberá procesar la imagen mediante el modelo YOLOv8 para detectar simultáneamente entre 1 y 3 productos.
*   **3.4.1.3** La aplicación deberá mostrar en la interfaz (Vista W2) el nombre, cantidad y precio unitario de los productos reconocidos.
*   **3.4.1.4** La aplicación deberá impedir el avance a la pasarela de pago si no detecta al menos un (1) producto válido.

**3.4.2 CONTROL Y VALIDACIÓN DE PESO (IOT)**
*   **3.4.2.1** La aplicación deberá leer el valor en gramos enviado por la celda de carga vía USB/Serial de forma continua.
*   **3.4.2.2** La aplicación deberá calcular el "Peso Teórico Total" sumando los pesos registrados en la base de datos de los ítems detectados.
*   **3.4.2.3** La aplicación deberá habilitar el botón "PAGAR" solo si la diferencia entre el Peso Físico y el Peso Teórico es ≤ 5 gramos.
*   **3.4.2.4** La aplicación deberá mostrar una alerta ("Revise su bandeja") si la diferencia de peso supera los 5 gramos, bloqueando el pago.

**3.4.3 INTERFAZ Y FLUJO DE USUARIO (UX/UI)**
*   **3.4.3.1** La aplicación deberá mostrar una pantalla de Inicio (W1) con el texto "[AUTO-CHECKOUT] Coloca tus productos" y el botón "INICIAR".
*   **3.4.3.2** La aplicación deberá mostrar un botón de "CORREGIR" en la Vista W3 para permitir al usuario retroceder si la lista es errónea.
*   **3.4.3.3** La aplicación deberá incluir un botón de "SOLICITAR AYUDA" siempre visible que emita una alerta a la caja principal.

**3.4.4 PROCESAMIENTO DE PAGO**
*   **3.4.4.1** La aplicación deberá generar y renderizar un código QR dinámico por el monto exacto de la transacción.
*   **3.4.4.2** La aplicación deberá consultar asíncronamente (webhook/polling) el estado del pago con la pasarela.
*   **3.4.4.3** La aplicación deberá mostrar el ticket ilustrativo (W4) únicamente al recibir confirmación exitosa (HTTP 200).
*   **3.4.4.4** La aplicación deberá reiniciar el flujo automáticamente hacia la pantalla de Inicio (W1) 10 segundos después de una compra exitosa.

---

## 3.5 Requisitos No Funcionales del Sistema

| ID | Categoría | Descripción del Requisito No Funcional |
| :--- | :--- | :--- |
| **RNF-01** | Rendimiento | La IA (Edge Computing) debe procesar la imagen y retornar la lista de productos en un máximo de **150 milisegundos**. |
| **RNF-02** | Usabilidad | El flujo completo (W1 a W4) debe poder ser completado por un usuario promedio en ≤ **45 segundos**. |
| **RNF-03** | Disponibilidad | El catálogo y lista de pesos debe operar desde una base de datos local (ej. SQLite) para tolerar cortes de internet. |
| **RNF-04** | Seguridad | Toda comunicación con APIs externas (pagos o nube) debe estar cifrada bajo protocolo TLS 1.3 (HTTPS). |
| **RNF-05** | Integridad | Las peticiones de validación de pago deben autenticarse usando tokens JWT firmados con clave asimétrica. |
| **RNF-06** | Diseño UI | La interfaz debe estar renderizada estrictamente para pantallas táctiles de formato vertical (Portrait) tipo quiosco. |
