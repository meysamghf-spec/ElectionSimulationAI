"use client";

import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

export interface ChartRow {
  name: string;
  value: number;
}

export function ChartCanvas({ rows, label }: { rows: ChartRow[]; label: string }) {
  return (
    <ResponsiveContainer width="100%" height={280}>
      <BarChart data={rows}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="name" interval={0} angle={-20} height={70} textAnchor="end" />
        <YAxis />
        <Tooltip />
        <Bar dataKey="value" name={label} fill="#0c5c56" />
      </BarChart>
    </ResponsiveContainer>
  );
}
