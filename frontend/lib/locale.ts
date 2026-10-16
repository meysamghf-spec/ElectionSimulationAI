/** Locale constants shared by server and client components. */

export type Locale = "fa" | "en";

/** Build-time default. English unless NEXT_PUBLIC_DEFAULT_LOCALE=fa. */
export const DEFAULT_LOCALE: Locale = process.env.NEXT_PUBLIC_DEFAULT_LOCALE === "fa" ? "fa" : "en";

export function directionOf(locale: Locale): "rtl" | "ltr" {
  return locale === "fa" ? "rtl" : "ltr";
}
