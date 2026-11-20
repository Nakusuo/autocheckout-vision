import { useEffect, useRef, useState } from "react";
import { formatPEN } from "../../format";
import { guideBox, toSuggestion, type Suggestion } from "../camara";

const SEND_EVERY_MS = 700;
const SEND_SIDE = 320; // px del recorte que viaja al servidor
const ADDED_COOLDOWN_MS = 1500; // tras AGREGAR, no se vuelve a sugerir lo mismo enseguida

/**
 * Cámara del navegador (laptop hoy, celular mañana): muestra la vista en vivo con un recuadro
 * guía, manda solo ese recuadro al quiosco cada ~0,7 s y ofrece AGREGAR el producto sugerido.
 */
export function CamaraWeb({ disabled, onAdd }: { disabled: boolean; onAdd: (sku: string) => void }) {
  const video = useRef<HTMLVideoElement>(null);
  const frame = useRef<HTMLDivElement>(null);
  const busy = useRef(false);
  const cooldown = useRef<{ sku: string; until: number } | null>(null);
  const [suggestion, setSuggestion] = useState<Suggestion | null>(null);
  const [cameraError, setCameraError] = useState<string | null>(() =>
    // Sin HTTPS (o localhost) el navegador no expone la cámara, aunque los tipos digan lo contrario
    typeof navigator.mediaDevices?.getUserMedia === "function" ? null : "Este navegador no permite usar la cámara (se necesita HTTPS o localhost)",
  );

  useEffect(() => {
    let stream: MediaStream | null = null;
    let stopped = false;
    const media = navigator.mediaDevices;
    if (typeof media?.getUserMedia !== "function") return; // el aviso ya está en cameraError
    media
      .getUserMedia({ video: { facingMode: { ideal: "environment" } }, audio: false })
      .then((s) => {
        if (stopped) {
          s.getTracks().forEach((t) => t.stop());
          return;
        }
        stream = s;
        if (video.current) {
          video.current.srcObject = s;
          void video.current.play?.();
        }
      })
      .catch(() => setCameraError("No se pudo abrir la cámara. Permite el acceso en el navegador."));

    const canvas = document.createElement("canvas");
    canvas.width = SEND_SIDE;
    canvas.height = SEND_SIDE;
    const timer = setInterval(() => {
      const v = video.current;
      const box = frame.current;
      if (busy.current || !v || !box || v.videoWidth === 0) return;
      const { x, y, side } = guideBox(v.videoWidth, v.videoHeight, box.clientWidth, box.clientHeight);
      const ctx = canvas.getContext("2d");
      if (!ctx) return;
      ctx.drawImage(v, x, y, side, side, 0, 0, SEND_SIDE, SEND_SIDE);
      busy.current = true;
      canvas.toBlob(
        (blob) => {
          if (!blob) {
            busy.current = false;
            return;
          }
          fetch("/api/vision/frame", { method: "POST", headers: { "Content-Type": "image/jpeg" }, body: blob })
            .then((r) => (r.ok ? r.json() : null))
            .then((body) => {
              if (stopped) return;
              const next = toSuggestion(body);
              const cool = cooldown.current;
              setSuggestion(next && cool && cool.sku === next.sku && Date.now() < cool.until ? null : next);
            })
            .catch(() => undefined)
            .finally(() => {
              busy.current = false;
            });
        },
        "image/jpeg",
        0.8,
      );
    }, SEND_EVERY_MS);

    return () => {
      stopped = true;
      clearInterval(timer);
      stream?.getTracks().forEach((t) => t.stop());
    };
  }, []);

  const add = (s: Suggestion) => {
    cooldown.current = { sku: s.sku, until: Date.now() + ADDED_COOLDOWN_MS };
    setSuggestion(null);
    onAdd(s.sku);
  };

  return (
    <div className="webcam">
      <div className="webcam-frame" ref={frame}>
        {cameraError ? (
          <p className="webcam-error" role="alert">{cameraError}</p>
        ) : (
          <video ref={video} className="webcam-video" autoPlay muted playsInline aria-label="Vista de la cámara" />
        )}
        <div className="webcam-box" aria-hidden="true" />
      </div>
      {suggestion ? (
        <div className="suggestion" role="status">
          <div className="suggestion-text">
            <span className="suggestion-name">{suggestion.name}</span>
            <span className="suggestion-price">{formatPEN(suggestion.price_cents)}</span>
          </div>
          <button type="button" className="btn btn-go btn-small suggestion-add" disabled={disabled} onClick={() => add(suggestion)}>
            AGREGAR
          </button>
        </div>
      ) : (
        <p className="hint webcam-hint">Pon un producto dentro del recuadro amarillo.</p>
      )}
    </div>
  );
}
