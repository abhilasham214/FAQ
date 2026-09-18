"use client";

import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

interface Props {
  data: { name: string; value: number }[];
  label: string;
  height?: number;
}

/** Horizontal bar chart: long category names stay readable. */
export function DistributionChart({ data, label, height = 260 }: Props) {
  return (
    <div role="img" aria-label={label} style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ left: 8, right: 24 }}>
          <CartesianGrid horizontal={false} stroke="#e2e8f0" />
          <XAxis type="number" allowDecimals={false} tick={{ fontSize: 12 }} />
          <YAxis
            type="category"
            dataKey="name"
            width={200}
            tick={{ fontSize: 12 }}
            tickFormatter={(v: string) => (v.length > 30 ? `${v.slice(0, 29)}…` : v)}
          />
          <Tooltip cursor={{ fill: "#f1f5f9" }} />
          <Bar dataKey="value" name="Tickets" fill="#4f46e5" radius={[0, 4, 4, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
