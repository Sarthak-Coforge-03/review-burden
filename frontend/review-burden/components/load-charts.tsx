"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { AXIS, type ChartPerson, colors, firstName, HEAVY, TOOLTIP } from "@/components/chart-theme";

/** One line per developer; `weeks` rows are keyed by person id. */
export function WeeklyReviewsChart({
  weeks,
  people,
}: {
  weeks: Array<{ label: string } & Record<string, number | string>>;
  people: ChartPerson[];
}) {
  const color = colors(people);
  return (
    <LineChart responsive data={weeks} style={{ width: "100%", height: 300 }} margin={{ top: 8, right: 16 }}>
      <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
      <XAxis dataKey="label" tick={AXIS} />
      <YAxis allowDecimals={false} tick={AXIS} width={32} />
      <Tooltip {...TOOLTIP} />
      <Legend />
      {people.map((p) => (
        <Line
          key={p.id}
          dataKey={String(p.id)}
          name={p.name}
          stroke={color.get(p.id)}
          strokeWidth={p.heavy ? 3 : 1.5}
          strokeOpacity={p.heavy ? 1 : 0.75}
          dot={false}
          isAnimationActive={false}
        />
      ))}
    </LineChart>
  );
}

/** Reviews in the load window per developer, with the median and the rule's "too many" line. */
export function WindowReviewsChart({
  rows,
  median,
  threshold,
  thresholdLabel,
}: {
  rows: Array<ChartPerson & { reviews: number }>;
  median: number;
  threshold: number;
  thresholdLabel: string;
}) {
  const color = colors(rows);
  return (
    <BarChart responsive data={rows} style={{ width: "100%", height: 300 }} margin={{ top: 20, right: 16 }}>
      <CartesianGrid strokeDasharray="3 3" opacity={0.2} vertical={false} />
      <XAxis dataKey="name" tick={AXIS} interval={0} tickFormatter={firstName} />
      <YAxis allowDecimals={false} tick={AXIS} width={32} domain={[0, (max: number) => Math.max(max, threshold * 1.1)]} />
      <Tooltip {...TOOLTIP} cursor={{ fillOpacity: 0.1 }} />
      <Bar dataKey="reviews" name="Reviews" isAnimationActive={false}>
        {rows.map((r) => (
          <Cell key={r.id} fill={color.get(r.id)} />
        ))}
      </Bar>
      <ReferenceLine
        y={median}
        stroke="currentColor"
        strokeDasharray="4 4"
        label={{ value: `median ${median}`, position: "insideTopRight", fill: "currentColor", fontSize: 12 }}
      />
      <ReferenceLine
        y={threshold}
        stroke={HEAVY}
        strokeDasharray="4 4"
        label={{ value: thresholdLabel, position: "insideTopRight", fill: HEAVY, fontSize: 12 }}
      />
    </BarChart>
  );
}
