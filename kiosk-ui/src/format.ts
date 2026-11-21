export function formatPEN(cents: number): string {
  return `S/ ${(cents / 100).toFixed(2)}`;
}

/** 987654321 → «987 654 321»: se lee mejor de pie. */
export const groupPhone = (digits: string) => digits.replace(/(\d{3})(?=\d)/g, "$1 ");

/** Fecha ISO de la boleta → «19/11/2026 21:05» (hora de Lima). Si no se entiende, tal cual. */
export function formatDateTime(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return new Intl.DateTimeFormat("es-PE", {
    timeZone: "America/Lima",
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(date);
}
