# Guion de sustentación (APF3, ~15 minutos)

Para el equipo. Cada bloque dice qué mostrar y qué decir; los números están medidos (las fuentes,
entre paréntesis). Antes de empezar: `./ops/publicar.sh` y abrir el QR en el celular.

## 1. Problema (1 min)

- Las bodegas pierden tiempo en caja con productos chicos y baratos. AutoCaja: el cliente pasa
  cada producto frente a la cámara, la pantalla lo agrega sola y paga con Yape.
- Requisitos que guían todo: reconocer en ≤ 150 ms por cuadro (RNF-01), funcionar sin internet
  en el local (RNF-03), cobrar solo lo validado (`SRS.md`).

## 2. Demo en vivo (3 min)

1. Celular: INICIAR → pasar 2 productos por el recuadro → se agregan solos («Agregado: …»).
2. Mostrar que un producto que no está en el catálogo **no** se agrega.
3. CONFIRMAR → PAGAR → QR de Yape.
4. En la PC, `/ayuda` con la clave: tocar SOLICITAR AYUDA en el celular → suena y aparece.
5. Decir con honestidad: la confirmación automática del pago espera a la app Android (no existe
   aún); las pruebas automáticas la simulan por API.

## 3. Criterio 2 — Búsqueda (2 min) · `BUSQUEDA.md`

- Tres problemas modelados como espacios de estados: el flujo W1–W4 (usa la máquina de estados
  real), «qué hay en la bandeja» por peso y los umbrales del reconocedor.
- A* expande 5 nodos frente a 11 de BFS en el flujo (heurística admisible); en el problema del
  peso la heurística es débil y BFS gana: **elegir según el problema**.
- Hill Climbing encuentra los umbrales óptimos con 17 evaluaciones (exhaustiva: 1581), pero fuera
  de muestra no generaliza mejor: **por eso no se cambió la regla**.

## 4. Criterio 3 — Regresión y logística (2 min) · `ml/MODELOS_APF3.md` §3–4

- Regresión: ms de DINOv2 según lado e hilos (405 mediciones). Lineal R² 0,886 → polinómica 0,964;
  Ridge/Lasso no aportan (la validación eligió α mínimo). Uso: el lado que cumple 150 ms.
- Logística «¿conocido?»: ROC-AUC 0,855 frente a 0,826 de la regla; el **margen pesa más** que el
  parecido. Se queda la regla por F1; la logística, si se quiere una probabilidad.
- Regresión para números (ms), clasificación para categorías (conocido/desconocido, SKU).

## 5. Criterio 4 — Clasificadores y ensambles (2 min) · `ml/MODELOS_APF3.md` §5

- Siete modelos, misma validación cruzada anidada y estratificada, F1 macro por el desbalance.
- Mejor: SVM lineal (F1 0,791, 0,06 ms). Los ensambles **arreglan al árbol** (0,43 → 0,57 bagging,
  0,68 boosting: varianza y sesgo) pero no le ganan al SVM en las huellas de DINOv2.
- Por qué el quiosco usa la galería (≈ KNN): admite productos nuevos sin reentrenar y puede decir
  «no lo conozco».

## 6. Criterio 1 — Cloud y DevOps (2 min) · `CLOUD_DEVOPS.md`, `NUBE.md`

- CI en cada PR: ruff, mypy, bandit, pruebas con cobertura ≥ 90 %, e2e, mutación, secretos y una
  compra completa en Docker. CD en `main`: imágenes en GHCR y despliegue.
- Edge frente a nube: la inferencia en el local (medido: 0,13 s local frente a 0,5–0,9 s por
  internet). Decisiones de costo: HF Spaces ya no es gratis, Cloud Run quedó listo con topes de
  gasto pero la tarjeta fue rechazada; se publica con un túnel de Cloudflare.

## 7. Criterio 5 — Trade-offs y limitaciones (2 min) · `TRADEOFFS.md`

- Pocos datos (107 fotos, 4–20 por producto) y de otra cámara: desviaciones grandes entre
  particiones.
- Sin balanza: ON-02 no medido; la alerta de seguridad mitiga.
- Pago: riesgo de un yapeo ajeno del mismo monto; mitigación propuesta: montos únicos.

## Preguntas probables

| Pregunta | Respuesta corta |
|---|---|
| ¿Por qué no entrenaron YOLO? | 107 fotos no alcanzan; la galería no necesita reentrenar (`TRADEOFFS.md` §4) |
| ¿Por qué no usan el SVM si es mejor? | Gana por poco con mucha varianza, no dice «no lo conozco» y hay que reentrenarlo por cada producto |
| ¿Validaron sin fuga de datos? | Validación anidada; la logística se valida por producto (GroupKFold) |
| ¿Qué es simulado? | La notificación de pago (sin app aún) y la pasarela QR de pruebas; todo lo demás se midió |
