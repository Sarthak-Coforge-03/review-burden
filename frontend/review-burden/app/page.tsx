import Link from "next/link";
import { Suspense } from "react";

import { HealthTrendChart } from "@/components/health-trend-chart";
import { ApiError, apiFetch } from "@/lib/api";
import type { HealthPart, HealthPartKey, Overview } from "@/lib/api-types";
import { duration, percent } from "@/lib/flag-format";

const WEEK_LABEL = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", timeZone: "UTC" });

export default function OverviewPage() {
  return (
    <section className="space-y-4">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold">Team overview</h1>
        <p className="max-w-2xl opacity-70">
          One score for how healthy code review is, built from the same checks as the flags, with what drives it and how
          it has moved week to week.
        </p>
      </div>
      <Suspense fallback={<div className="skeleton h-96 w-full" />}>
        <TeamOverview />
      </Suspense>
    </section>
  );
}

/** Score bands for color only; the score itself is the weighted average the API returns. */
function tone(score: number | null): "success" | "warning" | "error" | "neutral" {
  if (score === null) return "neutral";
  if (score >= 90) return "success";
  if (score >= 75) return "warning";
  return "error";
}

const TEXT = { success: "text-success", warning: "text-warning", error: "text-error", neutral: "opacity-60" };
const PROGRESS = {
  success: "progress-success",
  warning: "progress-warning",
  error: "progress-error",
  neutral: "",
};

const PARTS: Record<HealthPartKey, { label: string; href: string; link: string }> = {
  coverage: { label: "Coverage", href: "/flags?rule=merged_unreviewed&status=all", link: "Unreviewed merges" },
  depth: { label: "Depth", href: "/quality", link: "Review quality" },
  escapes: { label: "Escapes", href: "/quality", link: "Review quality" },
  responsiveness: { label: "Responsiveness", href: "/flags?rule=stale_backlog", link: "Stale reviews" },
  load_balance: { label: "Load balance", href: "/load", link: "Review load" },
};

function explain(part: HealthPart, overview: Overview): string {
  const { good, total } = part;
  const bad = total - good;
  if (total === 0) return "Nothing to measure in this window, so the other parts share its weight.";
  switch (part.key) {
    case "coverage":
      return `${good} of ${total} merged PRs were approved by someone other than the author before merging.`;
    case "depth":
      return `${bad} of ${total} big-PR approvals would be flagged as rubber stamps.`;
    case "escapes":
      return (
        `${bad} of ${total} approved PRs needed a revert or hotfix (${percent(bad / total)}); ` +
        `an escape rate of ${percent(overview.escape_rate_floor)} or more scores 0.`
      );
    case "responsiveness":
      return `${good} of ${total} review requests were answered within ${overview.stale_after_hours} hours.`;
    case "load_balance":
      return (
        `The two busiest reviewers did ${percent(bad / total)} of ${total} reviews; ` +
        `up to ${percent(overview.top2_share_threshold)} scores full marks.`
      );
  }
}

async function TeamOverview() {
  let overview: Overview;
  try {
    overview = await apiFetch<Overview>("/api/overview");
  } catch (error) {
    if (error instanceof ApiError && error.status === 403) {
      return (
        <div className="alert">
          Only the manager sees the team overview.{" "}
          <Link href="/me" className="link">
            See your own review debt and flags
          </Link>
        </div>
      );
    }
    return <div className="alert alert-error">Could not load the overview. Is the API running?</div>;
  }

  const { kpis } = overview;
  const scoreTone = tone(overview.score);
  const trend = overview.trend.map((t) => ({ label: WEEK_LABEL.format(new Date(t.as_of)), score: t.score }));
  const firstScore = overview.trend[0]?.score ?? null;
  const change = overview.score !== null && firstScore !== null ? overview.score - firstScore : null;

  return (
    <div className="space-y-6">
      <div className="grid gap-4 lg:grid-cols-3">
        <section className="card bg-base-100 shadow-sm">
          <div className="card-body items-center justify-center text-center">
            <h2 className="card-title text-base">Health score</h2>
            <div className={`text-6xl font-bold ${TEXT[scoreTone]}`}>{overview.score ?? "–"}</div>
            <p className="text-sm opacity-70">out of 100, last {overview.window_days} days</p>
            {change !== null && trend.length > 1 && (
              <p className="text-sm">
                {change === 0 ? "No change" : `${change > 0 ? "Up" : "Down"} ${Math.abs(change)}`} since{" "}
                {trend[0].label}
              </p>
            )}
          </div>
        </section>

        <section className="card bg-base-100 shadow-sm lg:col-span-2">
          <div className="card-body gap-3">
            <h2 className="card-title text-base">What makes up the score</h2>
            <ul className="space-y-3">
              {overview.parts.map((part) => {
                const partTone = tone(part.score);
                const meta = PARTS[part.key];
                return (
                  <li key={part.key} className="space-y-1">
                    <div className="flex items-baseline justify-between gap-4">
                      <span className="font-medium">
                        {meta.label}{" "}
                        <span className="text-xs font-normal opacity-60">{percent(part.weight)} weight</span>
                      </span>
                      <span className={`font-semibold ${TEXT[partTone]}`}>{part.score ?? "–"}</span>
                    </div>
                    <progress
                      className={`progress h-1.5 ${PROGRESS[partTone]}`}
                      value={part.score ?? 0}
                      max={100}
                      aria-label={`${meta.label} score`}
                    />
                    <p className="text-sm opacity-70">
                      {explain(part, overview)}{" "}
                      <Link href={meta.href} className="link">
                        {meta.link}
                      </Link>
                    </p>
                  </li>
                );
              })}
            </ul>
          </div>
        </section>
      </div>

      <div className="stats stats-vertical w-full bg-base-100 shadow-sm md:stats-horizontal">
        <Link href="/flags" className="stat hover:bg-base-200">
          <div className="stat-title">Open flags</div>
          <div className="stat-value">{kpis.open_flags}</div>
          <div className="stat-desc">Not yet acknowledged or dismissed</div>
        </Link>
        <div className="stat">
          <div className="stat-title">PRs merged</div>
          <div className="stat-value">{kpis.prs_merged}</div>
          <div className="stat-desc">Last {overview.window_days} days</div>
        </div>
        <div className="stat">
          <div className="stat-title">Time to first review</div>
          <div className="stat-value">
            {kpis.median_hours_to_first_review === null ? "–" : duration(kpis.median_hours_to_first_review * 3600)}
          </div>
          <div className="stat-desc">Median, PRs opened in the last {overview.window_days} days</div>
        </div>
        <Link href="/load" className="stat hover:bg-base-200">
          <div className="stat-title">Waiting reviews</div>
          <div className="stat-value">{kpis.waiting_reviews}</div>
          <div className={`stat-desc ${kpis.stale_reviews ? "text-error" : ""}`}>
            {kpis.stale_reviews} waiting over {overview.stale_after_hours} hours
          </div>
        </Link>
      </div>

      <section className="card bg-base-100 shadow-sm">
        <div className="card-body">
          <h2 className="card-title text-base">Score by week</h2>
          <p className="text-sm opacity-70">
            Each point is the score over the {overview.window_days} days up to that date.
          </p>
          <HealthTrendChart points={trend} />
        </div>
      </section>
    </div>
  );
}
