export function currency(value: number, compact = true): string {
  const isBillions = compact && Math.abs(value) >= 1_000_000_000;
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    notation: compact ? "compact" : "standard",
    minimumFractionDigits: isBillions ? 2 : 0,
    maximumFractionDigits: isBillions ? 2 : compact ? 1 : 0,
  }).format(value);
}

export function percent(value: number | null, digits = 0): string {
  if (value === null) return "—";
  return new Intl.NumberFormat("en-US", {
    style: "percent",
    maximumFractionDigits: digits,
  }).format(value);
}

export function titleCase(value: string): string {
  return value.replaceAll("_", " ").replace(/\b\w/g, (character) => character.toUpperCase());
}
