import { BOX_FRACTION, guideBox, toSuggestion } from "./camara";

describe("guideBox", () => {
  it("con la vista del mismo formato que el video, recorta el 60 % del alto, centrado", () => {
    // video 640×480 en un contenedor 4:3 de 320×240 → escala 0,5
    expect(guideBox(640, 480, 320, 240)).toEqual({ x: 176, y: 96, side: 288 });
  });

  it("si la vista recorta los lados del video (cover), sigue centrado en lo que se ve", () => {
    // video 1280×720 (16:9) en un contenedor 3:2 de 300×200: escala = max(300/1280, 200/720)
    const box = guideBox(1280, 720, 300, 200);
    expect(box.side).toBeCloseTo((BOX_FRACTION * 200) / (200 / 720));
    expect(box.x + box.side / 2).toBeCloseTo(640);
    expect(box.y + box.side / 2).toBeCloseTo(360);
  });

  it("nunca sale del video", () => {
    const box = guideBox(100, 100, 100, 100, 3);
    expect(box).toEqual({ x: 0, y: 0, side: 100 });
  });
});

describe("toSuggestion", () => {
  it("toma el producto cuando hay coincidencia", () => {
    expect(toSuggestion({ match: true, sku: "CASINO-43", name: "Casino", price_cents: 150, score: 1.3 })).toEqual({
      sku: "CASINO-43",
      name: "Casino",
      price_cents: 150,
    });
  });

  it.each([
    null,
    "texto",
    { match: false, sku: null, name: null, price_cents: null, score: 0.4 },
    { match: true, sku: "X", name: "Y" },
    { match: true, sku: 3, name: "Y", price_cents: 1 },
  ])("sin coincidencia clara no sugiere nada (%j)", (body) => {
    expect(toSuggestion(body)).toBeNull();
  });
});
