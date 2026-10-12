import type { Snapshot } from "../api";

export const SCREEN_NAME: Record<Snapshot["screen"], string> = {
  W1: "Inicio",
  W2: "Escaneando",
  W3: "Confirmar",
  QR: "Pago con QR",
  W4: "Ticket",
  FUERA_DE_SERVICIO: "Fuera de servicio",
};
