import { useEffect, useRef, useState, type CSSProperties } from "react";
import { AUTO_ADD_START, guideBox, STABLE_FRAMES, stepAutoAdd, toSuggestion, type Suggestion } from "../camara";
import { CheckDisc } from "../signs";

const SEND_EVERY_MS = 400;
const SEND_SIDE = 320; // px del recorte que viaja al servidor
const ADDED_SHOW_MS = 2200; // cuánto se ve «Agregado: …»
const FRAME_TIMEOUT_MS = 3000; // si la API no responde, se suelta el cuadro y se manda otro

type Status =
  | { kind: "idle" }
  | { kind: "seeing"; product: Suggestion; streak: number }
  | { kind: "added"; product: Suggestion };

const statusKey = (s: Status) =>
  s.kind === "idle" ? "idle" : `${s.kind}:${s.product.sku}:${s.kind === "seeing" ? s.streak : ""}`;

/**
 * Cámara del navegador (laptop hoy, celular mañana): muestra la vista en vivo con un recuadro
 * guía y manda solo ese recuadro al quiosco cada ~0,4 s. Cuando reconoce el mismo producto varias
 * veces seguidas, lo agrega solo (ver stepAutoAdd); si se equivoca, el cliente lo quita con «−».
 */
export function CamaraWeb({
  disabled,
  onAdd,
}: {
  disabled: boolean;
  /** Agrega el producto; resuelve true si la API lo aceptó. */
  onAdd: (sku: string) => Promise<boolean>;
}) {
  const video = useRef<HTMLVideoElement>(null);
  const frame = useRef<HTMLDivElement>(null);
  const busy = useRef(false);
  const auto = useRef(AUTO_ADD_START);
  // onAdd y disabled cambian con cada render; el temporizador lee siempre el valor actual
  const latest = useRef({ onAdd, disabled });
  const addedUntil = useRef(0);
  const [status, setStatus] = useState<Status>({ kind: "idle" });
  const [cameraError, setCameraError] = useState<string | null>(() =>
    // Sin HTTPS (o localhost) el navegador no expone la cámara, aunque los tipos digan lo contrario
    typeof navigator.mediaDevices?.getUserMedia === "function" ? null : "Este navegador no permite usar la cámara (se necesita HTTPS o localhost)",
  );

  useEffect(() => {
    latest.current = { onAdd, disabled };
  });

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

    // Solo se actualiza si cambia algo: evita un render (y un aviso al lector de pantalla) por cuadro
    const show = (next: Status) => setStatus((prev) => (statusKey(prev) === statusKey(next) ? prev : next));

    const handle = (product: Suggestion | null) => {
      // Si mientras viajaba el cuadro empezó a agregarse otro (o se cortó la conexión), se ignora:
      // contarlo como «vacío» podría agregar dos veces el producto que sigue en el recuadro.
      if (latest.current.disabled) return;
      const step = stepAutoAdd(auto.current, product?.sku ?? null);
      auto.current = step.state;
      if (step.add && product) {
        void latest.current.onAdd(step.add).then((ok) => {
          if (stopped || !ok) return; // si falló, el error ya se muestra en la pantalla
          addedUntil.current = Date.now() + ADDED_SHOW_MS;
          show({ kind: "added", product });
        });
      } else if (Date.now() < addedUntil.current) {
        // «Agregado» se queda un momento aunque el producto siga en el recuadro o ya haya salido
      } else if (product && product.sku !== step.state.lastAdded) {
        show({ kind: "seeing", product, streak: step.state.streak });
      } else {
        show({ kind: "idle" });
      }
    };

    const canvas = document.createElement("canvas");
    canvas.width = SEND_SIDE;
    canvas.height = SEND_SIDE;
    const ctx = canvas.getContext("2d");
    const timer = setInterval(() => {
      const v = video.current;
      const box = frame.current;
      // Sin enviar mientras se agrega, sin conexión o con la pestaña oculta: no serviría de nada
      if (busy.current || latest.current.disabled || document.hidden || !ctx || !v || !box || v.videoWidth === 0) return;
      const { x, y, side } = guideBox(v.videoWidth, v.videoHeight, box.clientWidth, box.clientHeight);
      ctx.drawImage(v, x, y, side, side, 0, 0, SEND_SIDE, SEND_SIDE);
      busy.current = true;
      canvas.toBlob(
        (blob) => {
          if (!blob) {
            busy.current = false;
            return;
          }
          fetch("/api/vision/frame", {
            method: "POST",
            headers: { "Content-Type": "image/jpeg" },
            body: blob,
            signal: AbortSignal.timeout(FRAME_TIMEOUT_MS),
          })
            .then((r) => (r.ok ? r.json() : null))
            .then((body) => {
              if (!stopped) handle(toSuggestion(body));
            })
            .catch(() => undefined)
            .finally(() => {
              busy.current = false;
            });
        },
        "image/jpeg",
        0.85,
      );
    }, SEND_EVERY_MS);

    return () => {
      stopped = true;
      clearInterval(timer);
      stream?.getTracks().forEach((t) => t.stop());
    };
  }, []);

  return (
    <div className="webcam">
      <div className={`webcam-frame ${status.kind}`} ref={frame}>
        {cameraError ? (
          <p className="webcam-error" role="alert">{cameraError}</p>
        ) : (
          <video ref={video} className="webcam-video" autoPlay muted playsInline aria-label="Vista de la cámara" />
        )}
        <div className="webcam-box" aria-hidden="true" />
      </div>
      <div className="webcam-status" role="status">
        {status.kind === "added" ? (
          <div className="scan-result added">
            <CheckDisc className="scan-result-icon" />
            <div className="scan-result-text">
              <span className="scan-result-name">Agregado: {status.product.name}</span>
              <span className="scan-result-hint">Sácalo del recuadro y pasa el siguiente.</span>
            </div>
          </div>
        ) : status.kind === "seeing" ? (
          <div className="scan-result seeing">
            <div className="scan-result-text">
              <span className="scan-result-name">{status.product.name}</span>
              <span className="scan-result-hint">Mantenlo quieto…</span>
            </div>
            <span
              className="scan-progress"
              aria-hidden="true"
              style={{ "--p": status.streak / STABLE_FRAMES } as CSSProperties}
            />
          </div>
        ) : (
          <p className="hint webcam-hint">Pon un producto dentro del recuadro amarillo.</p>
        )}
      </div>
    </div>
  );
}
