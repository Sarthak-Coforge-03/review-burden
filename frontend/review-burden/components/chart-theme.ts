// Shared Recharts styling. "Heavy" people (the ones a chart is about) get the error color.

export type ChartPerson = { id: number; name: string; heavy: boolean };

export const HEAVY = "var(--color-error)";
const PALETTE = ["#60a5fa", "#34d399", "#fbbf24", "#a78bfa", "#f472b6", "#2dd4bf", "#fb923c", "#94a3b8"];
export const AXIS = { stroke: "currentColor", fontSize: 12, opacity: 0.7 };
export const TOOLTIP = {
  contentStyle: {
    background: "var(--color-base-100)",
    border: "1px solid var(--color-base-300)",
  },
  labelStyle: { color: "var(--color-base-content)" },
};

export function colors(people: ChartPerson[]): Map<number, string> {
  let next = 0;
  return new Map(people.map((p) => [p.id, p.heavy ? HEAVY : PALETTE[next++ % PALETTE.length]]));
}
