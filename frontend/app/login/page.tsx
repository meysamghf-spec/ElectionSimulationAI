"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { ErrorText } from "@/components/ErrorText";
import { api } from "@/lib/api";
import type { SessionResponse } from "@/lib/types";

function safeNext(value: string | null): string {
  if (!value || !value.startsWith("/") || value.startsWith("//")) return "/history";
  return value;
}

function LoginForm() {
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
        <h1>Sign in</h1>
        <p>The session stays in an HttpOnly cookie. The password is not stored in this browser.</p>
      </header>
      <ErrorText error={error} />
      <form className="card stack" onSubmit={(event) => void submit(event)}>
        <label className="field">
          <span>Email</span>
          <input
            type="email"
            autoComplete="username"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
        </label>
        <label className="field">
          <span>Password</span>
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
            {pending ? "Signing in…" : "Sign in"}
          </button>
          {registrationOpen ? <Link href="/register">Create an account</Link> : null}
        </div>
      </form>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={<p>Loading sign-in…</p>}>
      <LoginForm />
    </Suspense>
  );
}
