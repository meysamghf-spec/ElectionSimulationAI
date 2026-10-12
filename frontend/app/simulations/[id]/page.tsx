"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api, downloadFile } from "@/lib/api";
import type { SensitivityReport, SimulationOutput } from "@/lib/types";
import { ResultsView } from "@/components/ResultsView";
import { ErrorText } from "@/components/ErrorText";

export default function ResultsPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const [output, setOutput] = useState<SimulationOutput | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [sensitivity, setSensitivity] = useState<SensitivityReport | null>(null);
  const [sensitivityError, setSensitivityError] = useState<unknown>(null);
  const [sensitivityLoading, setSensitivityLoading] = useState(false);
  const [downloadError, setDownloadError] = useState<unknown>(null);

  useEffect(() => {
    api<SimulationOutput>(`/simulations/${id}/results`)
      .then(setOutput)
      .catch(setError);
  }, [id]);

  async function runSensitivity() {
    setSensitivityLoading(true);
    setSensitivityError(null);
    try {
      const report = await api<SensitivityReport>(`/simulations/${id}/sensitivity`, { method: "POST" });
      setSensitivity(report);
    } catch (exc) {
      setSensitivityError(exc);
    } finally {
      setSensitivityLoading(false);
    }
  }

  async function download(path: string, filename: string) {
    setDownloadError(null);
    try {
      await downloadFile(path, filename);
    } catch (exc) {
      setDownloadError(exc);
    }
  }

  return (
    <div className="stack">
      <header className="page-head">
        <h1>Results</h1>
        <p>Charts and tables use the saved simulation response. They are not sample figures.</p>
      </header>
      <div className="button-row">
        <button type="button" onClick={() => void download(`/simulations/${id}/export.csv?view=candidates`, `simulation-${id}-candidates.csv`)}>
          Download candidate CSV
        </button>
        <button type="button" className="secondary" onClick={() => void download(`/simulations/${id}/export.csv?view=regional`, `simulation-${id}-regional.csv`)}>
          Download regional CSV
        </button>
        <button type="button" className="secondary" onClick={() => void download(`/simulations/${id}/export.json`, `simulation-${id}.json`)}>
          Download JSON
        </button>
        <button type="button" className="secondary" onClick={() => void download(`/simulations/${id}/export.pdf`, `simulation-${id}.pdf`)}>
          Download PDF
        </button>
        <a className="button secondary" href={`/simulations/${id}/compare`}>
          Compare scenarios
        </a>
      </div>
      <ErrorText error={downloadError} />
      <ErrorText error={error} />
      {!output && !error ? <p>Loading results…</p> : null}
      {output ? (
        <ResultsView
          output={output}
          simulationId={id}
          sensitivity={sensitivity}
          sensitivityLoading={sensitivityLoading}
          onSensitivity={() => void runSensitivity()}
          sensitivityError={sensitivityError}
        />
      ) : null}
    </div>
  );
}
