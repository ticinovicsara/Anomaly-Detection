export function pct(v: number | null): string {
  return v === null ? "-" : `${(v * 100).toFixed(1)}%`;
}

export function average(values: (number | null)[]): number | null {
  const present = values.filter((v): v is number => v !== null);
  if (present.length === 0) return null;
  return present.reduce((a, b) => a + b, 0) / present.length;
}
