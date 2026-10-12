import type { Flag, FlagStatus, RuleKey } from "./api-types";

export const RULE_LABELS: Record<RuleKey, string> = {
  merged_unreviewed: "Merged without review",
  merged_changes_pending: "Merged with changes requested",
  self_approval: "Self-approved",
  rubber_stamp: "Rubber-stamp approval",
  escape: "Escaped defect",
  stale_backlog: "Stale review request",
  load_concentration: "Review load concentrated",
};

export const STATUS_LABELS: Record<FlagStatus, string> = {
  open: "Open",
  acknowledged: "Acknowledged",
  dismissed: "Dismissed",
};

type NameOf = (id: number) => string;

function num(value: unknown): number {
  return typeof value === "number" ? value : Number(value ?? 0);
}

function ids(value: unknown): number[] {
  return Array.isArray(value) ? value.map(num) : [];
}

function plural(count: number, word: string): string {
  return `${count} ${word}${count === 1 ? "" : "s"}`;
}

function listNames(personIds: number[], nameOf: NameOf): string {
  const names = personIds.map(nameOf);
  return names.length <= 1 ? (names[0] ?? "someone") : `${names.slice(0, -1).join(", ")} and ${names.at(-1)}`;
}

function duration(seconds: number): string {
  if (seconds < 120) return plural(Math.round(seconds), "second");
  if (seconds < 2 * 3600) return plural(Math.round(seconds / 60), "minute");
  if (seconds < 48 * 3600) return `${(seconds / 3600).toFixed(1)} hours`;
  return `${(seconds / 86400).toFixed(1)} days`;
}

/** One plain-language sentence explaining why the flag fired, built from its evidence. */
export function describeEvidence(flag: Flag, nameOf: NameOf): string {
  const e = flag.evidence;
  switch (flag.rule_key) {
    case "merged_unreviewed":
      return `Merged with no review at all (${plural(num(e.lines), "line")} changed).`;
    case "merged_changes_pending":
      return `Merged while ${listNames(ids(e.pending_reviewer_ids), nameOf)} still had changes requested.`;
    case "self_approval":
      return "The author was the only person who approved it.";
    case "rubber_stamp": {
      const comments = num(e.substantive_comments);
      return (
        `Approved ${plural(num(e.lines), "changed line")} ${duration(num(e.seconds_to_approve))} after the PR opened, ` +
        `with ${comments === 0 ? "no substantive comments" : plural(comments, "substantive comment")}.`
      );
    }
    case "escape":
      return `Needed a ${e.kind === "revert" ? "revert" : "hotfix"} (#${num(e.fix_pr_id)}) soon after merging.`;
    case "stale_backlog":
      return `Review request unanswered for ${duration(num(e.waiting_hours) * 3600)}.`;
    case "load_concentration": {
      const share = Math.round(num(e.top2_share) * 100);
      const heavy = ids(e.over_median_multiple);
      const days = e.window_days === undefined ? "" : ` over the last ${num(e.window_days)} days`;
      const sentence = `The top two reviewers did ${share}% of reviews${days}`;
      return heavy.length === 0
        ? `${sentence}.`
        : `${sentence}; ${listNames(heavy, nameOf)} did far more than the median of ${num(e.median)}.`;
    }
  }
}

const DATE_FORMAT = new Intl.DateTimeFormat("en-GB", {
  day: "numeric",
  month: "short",
  year: "numeric",
  timeZone: "UTC",
});

export function formatDate(iso: string): string {
  return DATE_FORMAT.format(new Date(iso));
}
