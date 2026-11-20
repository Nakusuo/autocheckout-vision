export function formatPEN(cents: number): string {
  return `S/ ${(cents / 100).toFixed(2)}`;
}

/** 987654321 → «987 654 321»: se lee mejor de pie. */
export const groupPhone = (digits: string) => digits.replace(/(\d{3})(?=\d)/g, "$1 ");
