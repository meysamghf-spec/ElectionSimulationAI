"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ErrorText } from "@/components/ErrorText";
import { api } from "@/lib/api";
import type { MetaResponse, SessionResponse } from "@/lib/types";

export default function RegisterPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [pending, setPending] = useState(false);
  const [open, setOpen] = useState<boolean | null>(null);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const meta = await api<MetaResponse>("/meta");
        if (!cancelled) setOpen(meta.registration_open);
      } catch (exc) {
        if (!cancelled) {
          setOpen(false);
          setError(exc);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setPending(true);
    setError(null);
    try {
      await api<SessionResponse>("/auth/register", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      router.push("/history");
      router.refresh();
    } catch (exc) {
      setError(exc);
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="stack">
      <header className="page-head">
        <h1>Create an account</h1>
        <p>Passwords must be at least 12 characters. The server stores an Argon2 hash, not the password.</p>
      </header>
      <ErrorText error={error} />
      {open === false ? (
        <p className="notice">
          Registration is closed. An operator can create an account with the backend user command.{" "}
          <Link href="/login">Sign in</Link>
        </p>
      ) : null}
      {open ? (
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
              autoComplete="new-password"
              required
              minLength={12}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          </label>
          <div className="button-row">
            <button type="submit" disabled={pending}>
              {pending ? "Creating account…" : "Create account"}
            </button>
            <Link href="/login">Sign in instead</Link>
          </div>
        </form>
      ) : null}
    </div>
  );
}
