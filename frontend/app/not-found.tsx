"use client";

import Link from "next/link";
import { useI18n } from "@/lib/i18n";

export default function NotFound() {
  const { t } = useI18n();
  return (
    <div className="stack">
      <h1>{t("notfound.title")}</h1>
      <p>{t("notfound.lead")}</p>
      <Link className="button" href="/">
        {t("notfound.home")}
      </Link>
    </div>
  );
}
