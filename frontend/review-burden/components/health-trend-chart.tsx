"use client";

import { CartesianGrid, Line, LineChart, Tooltip, XAxis, YAxis } from "recharts";

import { AXIS, TOOLTIP } from "@/components/chart-theme";

/** `label` is preformatted on the server so client and server render the same text. */
export type TrendPoint = { label: string; score: number | null };

export function HealthTrendChart({ points }: { points: TrendPoint[] }) {
  const lowest = Math.min(100, ...points.flatMap((p) => (p.score === null ? [] : [p.score])));
  const floor = Math.max(0, Math.floor(lowest / 10) * 10 - 10);
  const ticks = Array.from({ length: (100 - floor) / 10 + 1 }, (_, i) => floor + i * 10);
  return (
    <LineChart responsive data={points} style={{ width: "100%", height: 240 }} margin={{ top: 8, right: 16 }}>
      <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
      <XAxis dataKey="label" tick={AXIS} />
      <YAxis domain={[floor, 100]} ticks={ticks} tick={AXIS} width={32} />
      <Tooltip {...TOOLTIP} />
      <Line
        dataKey="score"
        name="Health score"
        stroke="var(--color-info)"
        strokeWidth={2}
        dot={{ r: 3 }}
        isAnimationActive={false}
      />
    </LineChart>
  );
}
