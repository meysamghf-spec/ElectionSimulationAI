export function formatNumber(value: number | null | undefined, digits = 0): string {
  if (value == null || Number.isNaN(value)) return "—";
  return value.toLocaleString("en-US", {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  });
}

export function formatShare(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "—";
  return `${(value * 100).toFixed(2)}%`;
}

/** Absolute share change already expressed in percentage points. */
export function formatPercentagePoints(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "—";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)} pp`;
}

/** Relative change as a ratio, displayed as a percent of the baseline share. */
export function formatRelativeChange(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "—";
  const sign = value > 0 ? "+" : "";
  return `${sign}${(value * 100).toFixed(2)}%`;
}

export function formatSeconds(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "—";
  if (value < 10) return `${value.toFixed(2)} s`;
  return `${value.toFixed(1)} s`;
}
