export function formatPEN(cents: number): string {
  return `S/ ${(cents / 100).toFixed(2)}`;
}
