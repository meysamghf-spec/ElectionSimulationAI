"use client";

import { useI18n } from "@/lib/i18n";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  const { t } = useI18n();
  return (
    <div className="stack">
      <h1>{t("error.title")}</h1>
      <p>{error.message || t("error.unknown")}</p>
      <button type="button" onClick={() => reset()}>
        {t("error.retry")}
      </button>
    </div>
  );
}
