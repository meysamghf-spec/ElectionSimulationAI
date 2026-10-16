"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { ErrorText } from "@/components/ErrorText";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { SessionResponse } from "@/lib/types";

function safeNext(value: string | null): string {
  if (!value || !value.startsWith("/") || value.startsWith("//")) return "/history";
  return value;
}

function LoginForm() {
  const { t } = useI18n();
  const router = useRouter();
  const params = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [pending, setPending] = useState(false);
  const [registrationOpen, setRegistrationOpen] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setPending(true);
    setError(null);
    try {
      await api<SessionResponse>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      router.push(safeNext(params.get("next")));
      router.refresh();
    } catch (exc) {
      setError(exc);
      try {
        const meta = await api<{ registration_open: boolean }>("/meta");
        setRegistrationOpen(meta.registration_open);
      } catch {
        setRegistrationOpen(false);
      }
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="stack">
      <header className="page-head">
        <h1>{t("login.title")}</h1>
        <p>{t("login.lead")}</p>
      </header>
      <ErrorText error={error} />
      <form className="card stack" onSubmit={(event) => void submit(event)}>
        <label className="field">
          <span>{t("login.email")}</span>
          <input
            type="email"
            autoComplete="username"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
        </label>
        <label className="field">
          <span>{t("login.password")}</span>
          <input
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
        </label>
        <div className="button-row">
          <button type="submit" disabled={pending}>
            {pending ? t("login.pending") : t("login.submit")}
          </button>
          {registrationOpen ? <Link href="/register">{t("login.register")}</Link> : null}
        </div>
      </form>
    </div>
  );
}

function LoginFallback() {
  const { t } = useI18n();
  return <p>{t("login.loading")}</p>;
}

export default function LoginPage() {
  return (
    <Suspense fallback={<LoginFallback />}>
      <LoginForm />
    </Suspense>
  );
}
