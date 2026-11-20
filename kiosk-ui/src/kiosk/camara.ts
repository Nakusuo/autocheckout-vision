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

/** Cuadros seguidos con el mismo producto para agregarlo solo (~1,2 s a un cuadro cada 0,4 s). */
export const STABLE_FRAMES = 3;
/** Cuadros seguidos sin producto para dar por hecho que el anterior salió del recuadro. */
export const CLEAR_FRAMES = 2;

/**
 * Agregado automático: un producto se agrega cuando se reconoce igual varias veces seguidas, y
 * no vuelve a agregarse mientras siga en el recuadro. Para sumar otra unidad del mismo, se saca
 * y se vuelve a meter. Un parpadeo (un cuadro con otro producto) no agrega nada.
 */
export type AutoAdd = {
  candidate: string | null; // producto que se está viendo
  streak: number; // cuadros seguidos con ese producto
  empty: number; // cuadros seguidos sin producto
  lastAdded: string | null; // agregado y aún en el recuadro: no se repite
};

export const AUTO_ADD_START: AutoAdd = { candidate: null, streak: 0, empty: 0, lastAdded: null };

export function stepAutoAdd(state: AutoAdd, sku: string | null): { state: AutoAdd; add: string | null } {
  if (sku === null) {
    const empty = state.empty + 1;
    return {
      state: { candidate: null, streak: 0, empty, lastAdded: empty >= CLEAR_FRAMES ? null : state.lastAdded },
      add: null,
    };
  }
  const streak = sku === state.candidate ? state.streak + 1 : 1;
  if (streak >= STABLE_FRAMES && sku !== state.lastAdded) {
    return { state: { candidate: sku, streak: 0, empty: 0, lastAdded: sku }, add: sku };
  }
  return { state: { ...state, candidate: sku, streak, empty: 0 }, add: null };
}
