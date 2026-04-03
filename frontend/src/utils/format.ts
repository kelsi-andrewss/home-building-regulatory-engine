export function toTitleCase(str: string): string {
  return str
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (l) => l.toUpperCase());
}

export function formatValue(val: string | number | null): string {
  if (val === null || val === undefined) return 'N/A';
  return String(val);
}
