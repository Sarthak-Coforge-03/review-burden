import type { RuleSettings } from "@/lib/api-types";

export type SettingKey = keyof RuleSettings;
type NumberKey = Exclude<SettingKey, "stock_phrases" | "load_dedicated_reviewers">;

/** A form field for one setting. `percent` fields are shares (0-1) shown and typed as percentages. */
export type NumberField = {
  key: NumberKey;
  label: string;
  unit: string;
  percent?: boolean;
  step?: number;
  min?: number;
  max?: number;
};

export type SettingsGroup = {
  title: string;
  description: string;
  fields: NumberField[];
  phrases?: boolean;
  dedicatedReviewers?: boolean;
};

export const WEIGHT_KEYS: NumberKey[] = [
  "health_weight_coverage",
  "health_weight_depth",
  "health_weight_escapes",
  "health_weight_responsiveness",
  "health_weight_load_balance",
];

function weight(key: NumberKey, label: string): NumberField {
  return { key, label, unit: "%", percent: true, min: 0, max: 100 };
}

export const SETTINGS_GROUPS: SettingsGroup[] = [
  {
    title: "Rubber stamps",
    description: "An approval of a big PR that came too fast, or without a single substantive comment.",
    fields: [
      { key: "rubber_stamp_min_lines", label: "Big PR from", unit: "changed lines", min: 1 },
      { key: "rubber_stamp_max_seconds", label: "Too fast under", unit: "seconds", min: 0 },
    ],
  },
  {
    title: "Substantive comments",
    description: "A line comment at least this long that is not just a stock phrase.",
    fields: [{ key: "substantive_min_chars", label: "Minimum length", unit: "characters", min: 0 }],
    phrases: true,
  },
  {
    title: "Escapes and stale reviews",
    description: "A revert or hotfix soon after merging, and review requests left waiting.",
    fields: [
      { key: "escape_window_days", label: "Fix counts as an escape within", unit: "days of merging", min: 1, max: 365 },
      { key: "stale_after_hours", label: "Request is stale after", unit: "hours", min: 1 },
    ],
  },
  {
    title: "Review load",
    description: "Review work concentrated on a few people: the top two's share, or anyone far above the median.",
    fields: [
      { key: "load_window_days", label: "Window", unit: "days", min: 1, max: 365 },
      { key: "load_top2_share", label: "Top two above", unit: "% of reviews", percent: true, min: 1, max: 99 },
      { key: "load_median_multiple", label: "Anyone above", unit: "× the median", step: 0.1, min: 1 },
    ],
    dedicatedReviewers: true,
  },
  {
    title: "Repeat patterns",
    description: "The same rule firing for the same person again and again.",
    fields: [
      { key: "pattern_window_days", label: "Window", unit: "days", min: 1, max: 365 },
      { key: "pattern_min_count", label: "At least", unit: "flags", min: 2 },
      { key: "self_approval_pattern_window_days", label: "Self-approval window", unit: "days", min: 1, max: 365 },
      { key: "self_approval_pattern_min_count", label: "Self-approvals, at least", unit: "flags", min: 2 },
    ],
  },
  {
    title: "Health score",
    description: "The overview's score: five parts weighted together. The weights must add up to 100%.",
    fields: [
      { key: "health_window_days", label: "Measured over", unit: "days", min: 1, max: 365 },
      weight("health_weight_coverage", "Coverage weight"),
      weight("health_weight_depth", "Depth weight"),
      weight("health_weight_escapes", "Escapes weight"),
      weight("health_weight_responsiveness", "Responsiveness weight"),
      weight("health_weight_load_balance", "Load balance weight"),
      {
        key: "health_escape_rate_floor",
        label: "Escapes score 0 at",
        unit: "% escape rate",
        percent: true,
        min: 1,
        max: 100,
      },
    ],
  },
];

export const NUMBER_FIELDS: NumberField[] = SETTINGS_GROUPS.flatMap((g) => g.fields);

/** Settings as the form shows them: numbers as typed text, percentages scaled, phrases one per line,
 * dedicated reviewer ids comma-separated. */
export type FormValues = Record<SettingKey, string>;

export function toFormValues(settings: RuleSettings): FormValues {
  const values = {
    stock_phrases: settings.stock_phrases.join("\n"),
    load_dedicated_reviewers: settings.load_dedicated_reviewers.join(","),
  } as FormValues;
  for (const field of NUMBER_FIELDS) {
    const value = settings[field.key];
    values[field.key] = String(field.percent ? Math.round(value * 10000) / 100 : value);
  }
  return values;
}

export function fromFormValues(values: FormValues): RuleSettings {
  const settings = {
    stock_phrases: values.stock_phrases.split("\n"),
    load_dedicated_reviewers: dedicatedIds(values.load_dedicated_reviewers),
  } as RuleSettings;
  for (const field of NUMBER_FIELDS) {
    const value = Number(values[field.key]);
    settings[field.key] = field.percent ? value / 100 : value;
  }
  return settings;
}

export function dedicatedIds(value: string): number[] {
  return value.split(",").filter(Boolean).map(Number);
}

export function fieldLabel(key: string): string {
  if (key === "stock_phrases") return "Stock phrases";
  if (key === "load_dedicated_reviewers") return "Dedicated reviewers";
  return NUMBER_FIELDS.find((f) => f.key === key)?.label ?? key;
}
