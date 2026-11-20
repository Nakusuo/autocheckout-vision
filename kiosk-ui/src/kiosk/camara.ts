// Cálculos de la cámara del navegador (recuadro guía y respuesta del servidor).

/** Lado del recuadro guía, como fracción del alto visible de la cámara. */
export const BOX_FRACTION = 0.6;

export type Suggestion = { sku: string; name: string; price_cents: number };
type Box = { x: number; y: number; side: number };

/**
 * Recuadro guía en coordenadas del video. La vista muestra el video «cubriendo» un contenedor
 * de `cw`×`ch` (object-fit: cover) y el recuadro ocupa `fraction` del alto, centrado: se
 * recorta exactamente lo que el cliente ve dentro del recuadro.
 */
export function guideBox(vw: number, vh: number, cw: number, ch: number, fraction = BOX_FRACTION): Box {
  const scale = Math.max(cw / vw, ch / vh);
  const side = Math.min((fraction * ch) / scale, vw, vh);
  return { x: (vw - side) / 2, y: (vh - side) / 2, side };
}

/** Respuesta de /api/vision/frame → sugerencia, o null si no hay producto claro. */
export function toSuggestion(body: unknown): Suggestion | null {
  if (typeof body !== "object" || body === null) return null;
  const b = body as Record<string, unknown>;
  if (b.match !== true || typeof b.sku !== "string" || typeof b.name !== "string" || typeof b.price_cents !== "number") {
    return null;
  }
  return { sku: b.sku, name: b.name, price_cents: b.price_cents };
}
