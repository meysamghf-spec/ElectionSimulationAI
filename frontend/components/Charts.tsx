"use client";

import dynamic from "next/dynamic";
import type { ChartRow } from "./ChartCanvas";

const ChartCanvas = dynamic(() => import("./ChartCanvas").then((mod) => mod.ChartCanvas), {
  ssr: false,
  loading: () => <p>Loading chart…</p>,
});

export function BarPanel({
  title,
  rows,
  label,
  testId,
}: {
  title: string;
  rows: ChartRow[];
  label: string;
  testId: string;
}) {
  return (
    <figure className="chart-card">
      <figcaption>{title}</figcaption>
      <div data-testid={testId} data-values={rows.map((row) => row.value).join(",")}>
        <ChartCanvas rows={rows} label={label} />
      </div>
      <div className="table-wrap">
        <table>
          <caption>{title}</caption>
          <thead>
            <tr>
              <th scope="col">Name</th>
              <th scope="col">{label}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.name}>
                <td>{row.name}</td>
                <td>{row.value.toLocaleString("en-US")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </figure>
  );
}
