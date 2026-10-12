"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { HypotheticalBanner } from "./HypotheticalBanner";

const LINKS = [
  { href: "/new", label: "New simulation" },
  { href: "/prompt", label: "Prompt" },
  { href: "/configure", label: "Configuration" },
  { href: "/history", label: "History" },
  { href: "/import", label: "Import" },
  { href: "/help", label: "Help" },
  { href: "/settings", label: "Settings" },
];

export function Shell({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  const path = usePathname();

  return (
    <>
      <a className="skip-link" href="#main">
        Skip to content
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
            {open ? "Close menu" : "Menu"}
          </button>
          <nav id="site-nav" className={open ? "nav-links open" : "nav-links"} aria-label="Primary">
            {LINKS.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                aria-current={path === link.href ? "page" : undefined}
                onClick={() => setOpen(false)}
              >
                {link.label}
              </Link>
            ))}
          </nav>
        </div>
      </header>
      <HypotheticalBanner />
      <main id="main" className="page">
        {children}
      </main>
      <footer className="site-footer">
        <p>
          Hypothetical model output. Not an official result, poll, or forecast.{" "}
          <Link href="/privacy">Privacy and limitations</Link>
        </p>
      </footer>
    </>
  );
}
