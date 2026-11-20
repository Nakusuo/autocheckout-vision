# AutoCaja (autocheckout-vision)

Objetivo actual: **máxima nota en la rúbrica APF 3** (`docs/RUBRICA_APF3.md`). Qué falta y quién puede tomarlo: `docs/GUIA_EQUIPO.md` (tablero) y `docs/PLAN_APF3.md` (diseño de cada pieza).

## Grafo del proyecto (graphify)

`graphify-out/` contiene el grafo del código y de los documentos. **Antes de buscar en archivos, consúltalo:**

- Lee `graphify-out/GRAPH_REPORT.md` (resumen, comunidades, conceptos centrales).
- Pregunta con `/graphify query "<pregunta>"`, `/graphify path "A" "B"` o `/graphify explain "X"`.
- Las comunidades «TAREAS Criterio N» agrupan lo pendiente de cada criterio de la rúbrica.
- Tras cambiar código o documentos: `/graphify . --update` y sube `graphify-out/` en el mismo commit.

No hace falta clave de API. Instalación: `uv tool install graphifyy` (o `pipx install graphifyy`) y `graphify install`.

## Reglas

- Una rama por criterio, PR hacia `develop`. El CI debe pasar (ruff, mypy, bandit, cobertura ≥ 90 %).
- Todo algoritmo o modelo nuevo lleva pruebas y docstrings.
- Si algo se simuló o no se midió, se dice en el código y en el informe. No se inventan resultados.
- Los datos (`ml/data/`) y las claves nunca van a git.
