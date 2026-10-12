import Link from "next/link";
import { ApiError } from "@/lib/api";

export function ErrorText({ error }: { error: unknown }) {
  if (!error) return null;
  if (error instanceof ApiError) {
    return (
      <div className="error-box" role="alert">
        <p>{error.message}</p>
        {error.status === 401 ? (
          <p>
            <Link href="/login">Sign in</Link>
          </p>
        ) : null}
        {error.details.length > 0 ? (
          <ul>
            {error.details.map((detail, index) => (
              <li key={`${detail.field}-${index}`}>
                <strong>{detail.field}</strong>: {detail.message}
              </li>
            ))}
          </ul>
        ) : null}
      </div>
    );
  }
  const message = error instanceof Error ? error.message : "The request failed.";
  return (
    <div className="error-box" role="alert">
      <p>{message}</p>
    </div>
  );
}
