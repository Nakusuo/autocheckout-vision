#!/usr/bin/env bash
# Prende el quiosco en internet (plan B: PC + túnel de Cloudflare) y muestra su dirección con un
# código QR en la terminal, para abrirla desde el celular sin escribirla. Ver docs/NUBE.md.
#
#   ./ops/publicar.sh           # prende (si hace falta) y muestra la dirección y el QR
#   ./ops/publicar.sh apagar    # apaga el quiosco y el túnel (la dirección deja de existir)
#
# La dirección cambia cada vez que se prende el túnel: vuelve a correr el script para verla.
set -euo pipefail
cd "$(dirname "$0")/.."
COMPOSE=(docker compose -f docker-compose.publico.yml)

if [ "${1:-}" = "apagar" ]; then
  "${COMPOSE[@]}" down
  echo "Quiosco apagado."
  exit 0
fi

echo "Prendiendo el quiosco y el túnel (la primera vez tarda unos minutos)…"
if ! "${COMPOSE[@]}" up -d --build --wait >/dev/null 2>&1; then
  echo "No se pudo prender. Detalle:" >&2
  "${COMPOSE[@]}" up -d --build --wait
  exit 1
fi

URL=""
for _ in $(seq 1 30); do
  URL="$("${COMPOSE[@]}" logs tunel 2>&1 | grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' | tail -1 || true)"
  [ -n "$URL" ] && break
  sleep 2
done
if [ -z "$URL" ]; then
  echo "El túnel no dio una dirección. Mira: ${COMPOSE[*]} logs tunel" >&2
  exit 1
fi

# QR con OpenCV (ya está en el contenedor). Cada carácter «▀» pinta dos módulos: el de arriba
# con el color del texto y el de abajo con el del fondo, en blanco y negro fijos (se lee igual
# con la terminal en modo claro u oscuro).
"${COMPOSE[@]}" exec -T kiosco python - "$URL" <<'PY'
import sys

import cv2

qr = cv2.QRCodeEncoder.create().encode(sys.argv[1])
dark = qr < 128
rows, cols = dark.shape
pad = 2  # zona en blanco alrededor, la necesitan los lectores de QR
grid = [[False] * (cols + 2 * pad) for _ in range(pad)]
grid += [[False] * pad + list(r) + [False] * pad for r in dark]
grid += [[False] * (cols + 2 * pad) for _ in range(pad + 1)]
color = {True: "30", False: "37"}  # negro / blanco (texto)
back = {True: "40", False: "47"}  # negro / blanco (fondo)
for top, bottom in zip(grid[0::2], grid[1::2]):
    print("".join(f"\033[{color[t]};{back[b]}m▀" for t, b in zip(top, bottom)) + "\033[0m")
PY

cat <<FIN

  Quiosco (escanéalo con el celular):  $URL
  Caja:                                $URL/ayuda
  Clave de caja:                       grep KIOSK_CAJA_KEY .env

  Al terminar de presentar:            ./ops/publicar.sh apagar
FIN
