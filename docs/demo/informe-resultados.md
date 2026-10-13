# Informe de resultados — Demo AutoCaja (M5)

> Plantilla. Reemplaza cada `_(…)_` con datos medidos. Si algo no se midió, escribe «no medido» y la razón.

**Fecha:** _(dd/mm/aaaa)_ · **Lugar:** _(…)_ · **Equipo de la demo:** _(laptop, CPU, webcam)_
**Modo:** _(cámara por parecido (galería) / YOLOv8 / simulado)_ · **Versión:** _(commit de `develop`)_

## 1. Resumen

_(Tres o cuatro líneas: qué se probó, con cuántas personas y si se cumplen las metas.)_

## 2. Resultados frente al SRS

Pegar aquí la salida de `python -m kiosk.metrics`:

```
_(tabla de kiosk.metrics)_
```

| Meta | Requisito | Resultado | Cumple |
|---|---|---|---|
| ON-01 / RNF-02 | Compra de 1 a 3 productos en ≤ 45 s | _(media, máximo)_ | _(sí/no)_ |
| ON-02 | Pago solo con peso validado (±5 g) | _(alertas; prueba con peso escondido)_ | _(sí/no)_ |
| ON-03 | ≥ 80 % de compras sin ayuda | _(%)_ | _(sí/no)_ |
| RNF-01 | Inferencia ≤ 150 ms (p95) | _(ms de `python -m kiosk.recognizer medir` en el equipo de la demo)_ | _(sí/no)_ |
| Reconocimiento | Aciertos de `python -m kiosk.recognizer evaluar` (referencia con fotos del Drive: 91 % a 224 px, 88 % a 140 px) | _(% con la galería de la demo)_ | _(sí/no)_ |

## 3. Detalle por persona

| # | Productos | Tiempo (sistema) | Tiempo (cronómetro) | ¿Pidió ayuda? | Observaciones |
|---|---|---|---|---|---|
| 1 | _(…)_ | _(s)_ | _(s)_ | _(sí/no)_ | _(…)_ |
| 2 | | | | | |
| 3 | | | | | |
| 4 | | | | | |
| 5 | | | | | |

## 4. Observaciones

- **Lo que funcionó:** _(…)_
- **Dónde dudaron las personas:** _(pantalla y motivo)_
- **Errores o bloqueos:** _(…)_

## 5. Revisión legal

_(Resultado del checklist de la sección 4 del plan de M5.)_

## 6. Conclusiones y siguientes pasos

_(Qué se cumple, qué no, y qué haría falta para un piloto en tienda: balanza física, pasarela real, POS/SUNAT, más productos.)_
