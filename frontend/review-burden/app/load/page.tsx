import Link from "next/link";
import { Suspense } from "react";

import { WeeklyReviewsChart, WindowReviewsChart } from "@/components/load-charts";
import { ApiError, apiFetch } from "@/lib/api";
import type { LoadReport } from "@/lib/api-types";
import { duration, percent } from "@/lib/flag-format";

const WEEK_LABEL = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", timeZone: "UTC" });

export default function LoadPage() {
  return (
    <section className="space-y-4">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold">Review load</h1>
        <p className="max-w-2xl opacity-70">
          Who does the reviewing. Weekly reviews per developer, each person&apos;s share of recent reviews against
          the team median, and how long requests have been waiting on them.
        </p>
      </div>
      <Suspense fallback={<div className="skeleton h-96 w-full" />}>
        <Load />
      </Suspense>
    </section>
  );
}

async function Load() {
  let report: LoadReport;
  try {
    report = await apiFetch<LoadReport>("/api/load");
  } catch (error) {
    if (error instanceof ApiError && error.status === 403) {
      return <div className="alert">Only the manager sees the team&apos;s review load.</div>;
    }
    return <div className="alert alert-error">Could not load review load. Is the API running?</div>;
  }

  const people = report.people.map((r) => ({ id: r.person.id, name: r.person.name, heavy: r.over_median_multiple }));
  const weeks = report.week_starts.map((start, i) => ({
    label: WEEK_LABEL.format(new Date(start)),
    ...Object.fromEntries(report.people.map((r) => [String(r.person.id), r.weekly[i]])),
  }));
  const heavy = report.people.filter((r) => r.over_median_multiple);
  const dedicated = report.people.filter((r) => r.dedicated).map((r) => r.person.name);
  const multiple = report.median_multiple_threshold;

  return (
    <div className="space-y-6">
      {report.concentrated && (
        <div role="alert" className="alert alert-warning alert-soft">
          <div>
            <div className="font-medium">Review work is concentrated</div>
            <p className="text-sm">
              The two busiest reviewers did {percent(report.top2_share)} of the team&apos;s {report.team_reviews}{" "}
              reviews in the last {report.window_days} days (the rule allows {percent(report.top2_share_threshold)}).
              {heavy.map((r) => (
                <span key={r.person.id}>
                  {" "}
                  {r.person.name} did {r.median_multiple}× the median (the rule allows {multiple}×).
                </span>
              ))}{" "}
              <Link href="/flags?rule=load_concentration&status=all" className="link">
                See the flag
              </Link>
            </p>
          </div>
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <section className="card bg-base-100 shadow-sm">
          <div className="card-body">
            <h2 className="card-title text-base">Reviews per week</h2>
            <WeeklyReviewsChart weeks={weeks} people={people} />
          </div>
        </section>
        <section className="card bg-base-100 shadow-sm">
          <div className="card-body">
            <h2 className="card-title text-base">Reviews in the last {report.window_days} days</h2>
            <WindowReviewsChart
              rows={report.people.map((r, i) => ({ ...people[i], reviews: r.reviews }))}
              median={report.team_median}
              threshold={report.team_median * multiple}
              thresholdLabel={`${multiple}× median`}
            />
          </div>
        </section>
      </div>

      <div className="overflow-x-auto rounded-box bg-base-100">
        <table className="table">
          <thead>
            <tr>
              <th>Developer</th>
              <th className="text-right">Reviews, {report.window_days} days</th>
              <th className="text-right">Share</th>
              <th className="text-right">× median</th>
              <th className="text-right">Waiting on them</th>
              <th className="text-right">Oldest wait</th>
            </tr>
          </thead>
          <tbody>
            {report.people.map((r) => (
              <tr key={r.person.id}>
                <td>
                  <Link href={`/people/${r.person.id}`} className="link link-hover">
                    {r.person.name}
                  </Link>
                  {r.dedicated && <span className="badge badge-ghost badge-sm ms-2">Dedicated reviewer</span>}
                </td>
                <td className={`text-right ${r.over_median_multiple ? "font-semibold text-error" : ""}`}>{r.reviews}</td>
                <td className="text-right">{r.share === null ? "–" : percent(r.share)}</td>
                <td className={`text-right ${r.over_median_multiple ? "font-semibold text-error" : ""}`}>
                  {r.median_multiple === null ? "–" : `${r.median_multiple}×`}
                </td>
                <td className="text-right">{r.pending}</td>
                <td className="text-right">
                  {r.oldest_pending_hours === null ? "–" : duration(r.oldest_pending_hours * 3600)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-xs opacity-60">
        Team median: {report.team_median} reviews per developer over {report.window_days} days. The manager&apos;s
        reviews are not counted
        {dedicated.length > 0 && <>, and neither are the dedicated reviewers&apos; ({dedicated.join(", ")})</>}.
      </p>
    </div>
  );
}
