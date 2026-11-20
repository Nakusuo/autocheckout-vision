import { AUTO_ADD_START, BOX_FRACTION, guideBox, stepAutoAdd, toSuggestion, type AutoAdd } from "./camara";

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

describe("stepAutoAdd", () => {
  const run = (frames: (string | null)[]) => {
    let state: AutoAdd = AUTO_ADD_START;
    const added: string[] = [];
    for (const sku of frames) {
      const step = stepAutoAdd(state, sku);
      state = step.state;
      if (step.add) added.push(step.add);
    }
    return added;
  };

  it("agrega un producto visto 3 veces seguidas, una sola vez aunque siga en el recuadro", () => {
    expect(run(["CASINO", "CASINO"])).toEqual([]);
    expect(run(["CASINO", "CASINO", "CASINO"])).toEqual(["CASINO"]);
    expect(run(Array(12).fill("CASINO"))).toEqual(["CASINO"]);
  });

  it("un parpadeo con otro producto reinicia la cuenta y no agrega nada", () => {
    expect(run(["CASINO", "CANCUN", "CASINO", "CANCUN", "CASINO"])).toEqual([]);
  });

  it("para sumar otra unidad hay que sacarlo del recuadro y volver a meterlo", () => {
    const again = ["CASINO", "CASINO", "CASINO", null, "CASINO", "CASINO", "CASINO"];
    expect(run(again)).toEqual(["CASINO"]); // un solo cuadro vacío puede ser un parpadeo
    expect(run(["CASINO", "CASINO", "CASINO", null, null, "CASINO", "CASINO", "CASINO"])).toEqual(["CASINO", "CASINO"]);
  });

  it("si entra otro producto enseguida, también se agrega", () => {
    expect(run(["CASINO", "CASINO", "CASINO", "RITZ", "RITZ", "RITZ"])).toEqual(["CASINO", "RITZ"]);
  });
});
