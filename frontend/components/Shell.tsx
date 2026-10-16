"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import type { SessionResponse } from "@/lib/types";
import { I18nProvider, useI18n, type MessageKey } from "@/lib/i18n";
import { HypotheticalBanner } from "./HypotheticalBanner";

const LINKS: { href: string; label: MessageKey }[] = [
  { href: "/new", label: "nav.new" },
  { href: "/prompt", label: "nav.prompt" },
  { href: "/configure", label: "nav.configure" },
  { href: "/history", label: "nav.history" },
  { href: "/import", label: "nav.import" },
  { href: "/help", label: "nav.help" },
  { href: "/settings", label: "nav.settings" },
];

export function Shell({ children }: { children: React.ReactNode }) {
  return (
    <I18nProvider>
      <ShellFrame>{children}</ShellFrame>
    </I18nProvider>
  );
}

function ShellFrame({ children }: { children: React.ReactNode }) {
  const { t, locale, setLocale } = useI18n();
  const [open, setOpen] = useState(false);
  const [session, setSession] = useState<SessionResponse | null>(null);
  const path = usePathname();
  const router = useRouter();

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const payload = await api<SessionResponse>("/auth/me");
        if (!cancelled) setSession(payload);
      } catch {
        if (!cancelled) setSession(null);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [path]);

  async function logout() {
    try {
      await api("/auth/logout", { method: "POST" });
    } catch {
      // The session is already gone, or this server does not use accounts.
    }
    setSession(null);
    setOpen(false);
    router.push("/login");
    router.refresh();
  }

  return (
    <>
      <a className="skip-link" href="#main">
        {t("skip")}
      </a>
      <header className="site-header">
        <div className="header-inner">
          <Link className="wordmark" href="/">
            ElectionSimulationAI
          </Link>
          <button
            type="button"
            className="nav-toggle"
            aria-expanded={open}
            aria-controls="site-nav"
            onClick={() => setOpen((value) => !value)}
          >
            {open ? t("menu.close") : t("menu.open")}
          </button>
          <nav id="site-nav" className={open ? "nav-links open" : "nav-links"} aria-label="Primary">
            {LINKS.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                aria-current={path === link.href ? "page" : undefined}
                onClick={() => setOpen(false)}
              >
                {t(link.label)}
              </Link>
            ))}
            {session?.auth_mode === "accounts" && session.authenticated ? (
              <>
                <span>{session.email}</span>
                <button type="button" className="secondary" onClick={() => void logout()}>
                  {t("nav.signout")}
                </button>
              </>
            ) : null}
            {session?.auth_mode === "accounts" && !session.authenticated ? (
              <Link href="/login" onClick={() => setOpen(false)}>
                {t("nav.signin")}
              </Link>
            ) : null}
            <button
              type="button"
              className="secondary lang-toggle"
              aria-label={t("lang.switchLabel")}
              onClick={() => setLocale(locale === "fa" ? "en" : "fa")}
            >
              {t("lang.switch")}
            </button>
          </nav>
        </div>
      </header>
      <HypotheticalBanner />
      <main id="main" className="page">
        {children}
      </main>
      <footer className="site-footer">
        <p>
          {t("footer")} <Link href="/privacy">{t("footer.privacy")}</Link>
        </p>
      </footer>
    </>
  );
}
