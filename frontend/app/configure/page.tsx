"use client";

import dynamic from "next/dynamic";
import { Suspense } from "react";

const ConfigureEditor = dynamic(
  () => import("@/components/ConfigureEditor").then((mod) => mod.ConfigureEditor),
  { ssr: false, loading: () => <p>Loading configuration…</p> },
);

export default function ConfigurePage() {
  return (
    <Suspense fallback={<p>Loading configuration…</p>}>
      <ConfigureEditor />
    </Suspense>
  );
}
