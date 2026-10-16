"use client";

import { useI18n } from "@/lib/i18n";

/** Always-visible notice that every number on the site is simulated, not a real prediction. */
export function HypotheticalBanner() {
  const { t, locale } = useI18n();
  return (
    <div className="hypothetical-banner" role="note" data-testid="simulation-disclaimer">
      <strong>{t("banner")}</strong>
      {locale === "fa" ? (
        <span className="banner-secondary" lang="en" dir="ltr">
          Simulation only: hypothetical results, not official results, polls, or real predictions.
        </span>
      ) : null}
    </div>
  );
}
