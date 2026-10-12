"use client";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="stack">
      <h1>This page failed to render</h1>
      <p>{error.message || "An unexpected error occurred."}</p>
      <button type="button" onClick={() => reset()}>
        Try again
      </button>
    </div>
  );
}
