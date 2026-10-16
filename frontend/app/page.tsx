"use client";

import Link from "next/link";
import { useI18n } from "@/lib/i18n";

export default function HomePage() {
  const { t, locale } = useI18n();
  return (
    <div className="stack">
      <header className="page-head">
        <p className="eyebrow">{t("home.eyebrow")}</p>
        <h1>{t("home.title")}</h1>
        <p>{t("home.lead")}</p>
      </header>
      <ol className="steps">
        <li>{t("home.step1")}</li>
        <li>{t("home.step2")}</li>
        <li>{t("home.step3")}</li>
        <li>{t("home.step4")}</li>
        <li>{t("home.step5")}</li>
      </ol>
      <div className="button-row">
        <Link className="button" href="/new">
          {t("home.start")}
        </Link>
        <Link className="button secondary" href="/help">
          {t("home.method")}
        </Link>
      </div>
      <section className="card stack">
        <h2>{t("home.what")}</h2>
        <ul>
          <li>{t("home.f1")}</li>
          <li>{t("home.f2")}</li>
          <li>{t("home.f3")}</li>
          <li>{t("home.f4")}</li>
        </ul>
        <p>{t("home.not")}</p>
        {locale === "fa" ? <p className="muted">{t("partial")}</p> : null}
      </section>
    </div>
  );
}
