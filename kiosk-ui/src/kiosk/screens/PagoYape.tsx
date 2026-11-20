import { useState } from "react";
import type { Snapshot } from "../../api";
import { formatPEN, groupPhone } from "../../format";
import { CancelButton } from "../CancelButton";
import { ArrowRight, BackspaceGlyph } from "../signs";
import { useAction } from "../useAction";
import { Alert } from "./Alert";

const PHONE_DIGITS = 9;
const OTP_DIGITS = 6;
const KEYS = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "borrar", "0", "limpiar"] as const;

type Field = "phone" | "otp";

/**
 * Cobro con Yape (vía Mercado Pago): el cliente escribe su celular y el código de aprobación
 * que le muestra su app Yape. Pantalla táctil: teclado numérico propio, sin teclado del sistema.
 */
export function PagoYape({ snapshot, offline }: { snapshot: Snapshot; offline: boolean }) {
  const { error, pending, run } = useAction();
  const [phone, setPhone] = useState("");
  const [otp, setOtp] = useState("");
  const [field, setField] = useState<Field>("phone");
  const processing = pending || snapshot.payment_processing === true;
  const rejection = snapshot.payment_error ?? null;
  const left = Math.max(0, Math.ceil(120 - snapshot.seconds_in_state));

  const value = field === "phone" ? phone : otp;
  const max = field === "phone" ? PHONE_DIGITS : OTP_DIGITS;
  const setValue = field === "phone" ? setPhone : setOtp;

  const press = (key: (typeof KEYS)[number]) => {
    if (key === "borrar") return setValue(value.slice(0, -1));
    if (key === "limpiar") return setValue("");
    if (value.length >= max) return;
    const next = value + key;
    setValue(next);
    if (field === "phone" && next.length === PHONE_DIGITS) setField("otp");
  };

  const message = rejection ?? error;
  const ready = phone.length === PHONE_DIGITS && otp.length === OTP_DIGITS;

  return (
    <section className="screen screen-yape">
      <div className="yape-head">
        <div className="pay-head">
          <p className="pay-label">Total a pagar con Yape</p>
          <p className="amount">{formatPEN(snapshot.total_cents)}</p>
        </div>
        <p className="speed-sign" role="timer" aria-label={`Quedan ${left} segundos para pagar`}>{left} s</p>
      </div>

      <div className="yape-fields">
        <button
          type="button"
          className={`yape-field${field === "phone" ? " active" : ""}`}
          aria-pressed={field === "phone"}
          disabled={processing}
          onClick={() => setField("phone")}
        >
          <span className="yape-field-label">Celular</span>
          <span className="yape-field-value" data-testid="yape-phone">
            {phone ? groupPhone(phone) : "9 dígitos"}
          </span>
        </button>
        <button
          type="button"
          className={`yape-field${field === "otp" ? " active" : ""}`}
          aria-pressed={field === "otp"}
          disabled={processing}
          onClick={() => setField("otp")}
        >
          <span className="yape-field-label">Código de aprobación</span>
          <span className="yape-field-value" data-testid="yape-otp">
            {otp || "6 dígitos"}
          </span>
        </button>
      </div>
      {/* Un solo renglón de mensaje bajo los campos: estado, rechazo o la pista. Así la pantalla
          no crece y CANCELAR nunca queda tapado. */}
      {processing ? (
        <p className="pay-hint" role="status">Procesando pago con Yape…</p>
      ) : message ? (
        <Alert>{message}</Alert>
      ) : (
        <p className="hint">En tu app Yape: menú → «Código de aprobación» (dura 2 min).</p>
      )}

      <div className="keypad" role="group" aria-label={field === "phone" ? "Teclado: celular" : "Teclado: código"}>
        {KEYS.map((key) => (
          <button
            key={key}
            type="button"
            className={`key${key.length > 1 ? " key-text" : ""}`}
            disabled={processing}
            aria-label={key === "borrar" ? "Borrar un dígito" : key === "limpiar" ? "Borrar todo" : undefined}
            onClick={() => press(key)}
          >
            {key === "borrar" ? <BackspaceGlyph className="key-icon" /> : key === "limpiar" ? "Borrar" : key}
          </button>
        ))}
      </div>

      <div className="actions yape-actions">
        <button
          type="button"
          className="btn btn-go"
          disabled={offline || processing || !ready}
          onClick={() => {
            // El código es de un solo uso: si Yape rechaza, el cliente escribe uno nuevo.
            run("/api/pay/yape", { phone, otp });
            setOtp("");
            setField("otp");
          }}
        >
          PAGAR CON YAPE
          <ArrowRight className="btn-icon" />
        </button>
        <CancelButton disabled={offline || processing} onCancel={() => run("/api/cancel")} />
      </div>
    </section>
  );
}
