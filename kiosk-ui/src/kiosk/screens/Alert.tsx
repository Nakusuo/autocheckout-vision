import { CautionDiamond } from "../signs";

/** Aviso de precaución: placa amarilla con el rombo. El texto lleva el mensaje. */
export function Alert({ children }: { children: string }) {
  return (
    <p className="alert" role="alert">
      <CautionDiamond className="alert-icon" />
      <span>{children}</span>
    </p>
  );
}
