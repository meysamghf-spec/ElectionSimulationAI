/** Locale constants shared by server and client components. */

export type Locale = "fa" | "en";

/** Build-time default. Persian unless NEXT_PUBLIC_DEFAULT_LOCALE=en. */
export const DEFAULT_LOCALE: Locale = process.env.NEXT_PUBLIC_DEFAULT_LOCALE === "en" ? "en" : "fa";

export function directionOf(locale: Locale): "rtl" | "ltr" {
  return locale === "fa" ? "rtl" : "ltr";
}
