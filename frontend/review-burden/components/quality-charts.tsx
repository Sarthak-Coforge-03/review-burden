"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  LabelList,
  ReferenceLine,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { AXIS, type ChartPerson, colors, firstName, HEAVY } from "@/components/chart-theme";

/** `detail` is preformatted on the server so client and server render the same text. */
export type SpeedPoint = ChartPerson & { minutes: number; substantive: number; detail: string };
export type EscapePoint = ChartPerson & { rate: number; detail: string };

type DetailPayload = ReadonlyArray<{ payload?: ChartPerson & { detail: string } }>;

function DetailTooltip({ active, payload }: { active?: boolean; payload?: DetailPayload }) {
  const point = payload?.[0]?.payload;
  if (!active || !point) return null;
  return (
    <div className="rounded-box border border-base-300 bg-base-100 px-3 py-2 text-sm shadow-sm">
      <div className="font-medium">{point.name}</div>
      <div className="opacity-70">{point.detail}</div>
    </div>
  );
}

/** Approval speed (x, minutes per 100 lines) against substantive comment share (y, percent). Fast and quiet is bottom-left. */
export function SpeedVsDepthChart({
  points,
  medianMinutes,
  medianSubstantive,
}: {
  points: SpeedPoint[];
  medianMinutes: number | null;
  medianSubstantive: number | null;
}) {
  const color = colors(points);
  const heavy = points.filter((p) => p.heavy);
  return (
    <div>
      <ScatterChart responsive style={{ width: "100%", height: 320 }} margin={{ top: 16, right: 48, bottom: 16 }}>
        <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
        <XAxis
          type="number"
          dataKey="minutes"
          name="Minutes per 100 lines"
          tick={AXIS}
          domain={[0, "auto"]}
          label={{
            value: "minutes to approve, per 100 lines",
            position: "insideBottom",
            offset: -8,
            fontSize: 12,
            fill: "currentColor",
          }}
        />
        <YAxis
          type="number"
          dataKey="substantive"
          name="Substantive comments"
          tick={AXIS}
          width={44}
          unit="%"
          domain={[(min: number) => Math.max(0, Math.floor(min / 10) * 10 - 10), 100]}
          tickCount={6}
        />
        <Tooltip content={DetailTooltip} cursor={{ strokeDasharray: "3 3" }} />
        {medianMinutes !== null && (
          <ReferenceLine
            x={medianMinutes}
            stroke="currentColor"
            strokeDasharray="4 4"
            label={{
              value: "median",
              position: "insideTopRight",
              fill: "currentColor",
              fontSize: 12,
            }}
          />
        )}
        {medianSubstantive !== null && (
          <ReferenceLine y={medianSubstantive} stroke="currentColor" strokeDasharray="4 4" />
        )}
        <Scatter data={points} isAnimationActive={false}>
          {points.map((p) => (
            <Cell key={p.id} fill={color.get(p.id)} />
          ))}
        </Scatter>
        {/* Most points sit in a tight cluster, so only the people the chart is about get a name label. */}
        <Scatter data={heavy} fill={HEAVY} isAnimationActive={false}>
          <LabelList dataKey="name" position="right" fill={HEAVY} fontSize={12} />
        </Scatter>
      </ScatterChart>
      <ul className="flex flex-wrap justify-center gap-x-4 gap-y-1 text-xs">
        {points.map((p) => (
          <li key={p.id} className="flex items-center gap-1.5">
            <span className="inline-block size-2.5 rounded-full" style={{ background: color.get(p.id) }} />
            {p.name}
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Share of approved, merged PRs that needed a revert or hotfix, per developer. */
export function EscapeRateChart({ points }: { points: EscapePoint[] }) {
  const color = colors(points);
  return (
    <BarChart responsive data={points} style={{ width: "100%", height: 320 }} margin={{ top: 20, right: 16 }}>
      <CartesianGrid strokeDasharray="3 3" opacity={0.2} vertical={false} />
      <XAxis dataKey="name" tick={AXIS} interval={0} tickFormatter={firstName} />
      <YAxis tick={AXIS} width={44} unit="%" allowDecimals={false} />
      <Tooltip content={DetailTooltip} cursor={{ fillOpacity: 0.1 }} />
      <Bar dataKey="rate" isAnimationActive={false}>
        {points.map((p) => (
          <Cell key={p.id} fill={color.get(p.id)} />
        ))}
      </Bar>
    </BarChart>
  );
}
