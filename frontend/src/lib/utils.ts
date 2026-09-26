export function cn(...values: Array<string | false | null | undefined>): string {
  return values.filter(Boolean).join(" ");
}

export function humanize(value: string | undefined): string {
  if (!value) return "Unknown";
  return value
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function formatNumber(value: string | number | null | undefined): string {
  if (typeof value === "number") {
    return Number.isInteger(value) ? String(value) : value.toFixed(3).replace(/0+$/, "").replace(/\.$/, "");
  }
  return value == null ? "—" : String(value);
}

export function isEvidenceCovered(value: boolean | string | number | null): boolean {
  return value === true || value === "covered" || value === "available" || value === 1;
}
