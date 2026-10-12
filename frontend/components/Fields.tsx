"use client";

import { useEffect, useRef, useState } from "react";

export function NumberField({
  label,
  value,
  onValue,
  hint,
  integer = false,
}: {
  label: string;
  value: number;
  onValue: (value: number) => void;
  hint?: string;
  integer?: boolean;
}) {
  const [text, setText] = useState(String(value));
  const [error, setError] = useState<string | null>(null);
  const focused = useRef(false);

  useEffect(() => {
    if (!focused.current) setText(String(value));
  }, [value]);

  return (
    <label className="field">
      <span>{label}</span>
      <input
        inputMode={integer ? "numeric" : "decimal"}
        value={text}
        aria-invalid={error ? true : undefined}
        onFocus={() => {
          focused.current = true;
        }}
        onBlur={() => {
          focused.current = false;
          if (!error) setText(String(value));
        }}
        onChange={(event) => {
          const next = event.target.value;
          setText(next);
          if (next.trim() === "") {
            setError("Enter a number. The stored value stays unchanged until this field is valid.");
            return;
          }
          const parsed = Number(next);
          if (!Number.isFinite(parsed) || (integer && !Number.isInteger(parsed))) {
            setError(
              integer
                ? "Enter a whole number. The stored value was not changed."
                : "Enter a number. The stored value was not changed.",
            );
            return;
          }
          setError(null);
          onValue(parsed);
        }}
      />
      {hint ? <small className="hint">{hint}</small> : null}
      {error ? <small className="field-error">{error}</small> : null}
    </label>
  );
}

export function TextField({
  label,
  value,
  onValue,
  hint,
}: {
  label: string;
  value: string;
  onValue: (value: string) => void;
  hint?: string;
}) {
  return (
    <label className="field">
      <span>{label}</span>
      <input value={value} onChange={(event) => onValue(event.target.value)} />
      {hint ? <small className="hint">{hint}</small> : null}
    </label>
  );
}
