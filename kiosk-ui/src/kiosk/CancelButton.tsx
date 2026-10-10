/** Cancelar la compra: vuelve al inicio y descarta la lista (y el cobro, si ya había QR). */
export function CancelButton({ disabled, onCancel }: { disabled: boolean; onCancel: () => void }) {
  return (
    <button type="button" className="btn btn-cancel" disabled={disabled} onClick={onCancel}>
      CANCELAR COMPRA
    </button>
  );
}
