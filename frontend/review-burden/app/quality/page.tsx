import Link from "next/link";
import { Suspense } from "react";

import { EscapeRateChart, SpeedVsDepthChart } from "@/components/quality-charts";
import { ApiError, apiFetch } from "@/lib/api";
import type { QualityReport, QualityRow } from "@/lib/api-types";
import { duration, formatDate, percent } from "@/lib/flag-format";

export default function QualityPage() {
  return (
    <section className="space-y-4">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold">Review quality</h1>
        <p className="max-w-2xl opacity-70">
          How each developer reviews: how fast they approve for the size of the change, how much of what they say is
          substantive, how often they wave big PRs through, and how often work they approved had to be reverted or
          hotfixed.
        </p>
      </div>
      <Suspense fallback={<div className="skeleton h-96 w-full" />}>
        <Quality />
      </Suspense>
    </section>
  );
}

const speed = (minutes: number | null) => (minutes === null ? "–" : duration(minutes * 60));
const share = (value: number | null) => (value === null ? "–" : percent(value));

/** Most of their big approvals would be flagged as rubber stamps. */
function stampsBigPrs(r: QualityRow): boolean {
  return r.big_approvals > 0 && r.stamped_big_approvals * 2 > r.big_approvals;
}

function flagsHref(rule: "rubber_stamp" | "escape", personId: number): string {
  return `/flags?status=all&rule=${rule}&person=${personId}`;
}

async function Quality() {
  let report: QualityReport;
  try {
    report = await apiFetch<QualityReport>("/api/quality");
  } catch (error) {
    if (error instanceof ApiError && error.status === 403) {
      return <div className="alert">Only the manager sees the team&apos;s review quality.</div>;
    }
    return <div className="alert alert-error">Could not load review quality. Is the API running?</div>;
  }

  const { medians } = report;
  const people = report.people.map((r) => ({
    id: r.person.id,
    name: r.person.name,
    heavy: stampsBigPrs(r),
  }));
  const speedPoints = report.people.flatMap((r, i) =>
    r.minutes_per_100_lines === null || r.substantive_share === null
      ? []
      : [
          {
            ...people[i],
            minutes: r.minutes_per_100_lines,
            substantive: Math.round(r.substantive_share * 100),
            detail: `${speed(r.minutes_per_100_lines)} per 100 lines, ${percent(r.substantive_share)} substantive`,
          },
        ],
  );
  const escapePoints = report.people.flatMap((r, i) =>
    r.escape_rate === null
      ? []
      : [
          {
            ...people[i],
            rate: Math.round(r.escape_rate * 1000) / 10,
            detail: `${r.escapes} of ${r.approved_merged} approved PRs needed a fix`,
          },
        ],
  );
  const stampers = report.people.filter(stampsBigPrs);

  return (
    <div className="space-y-6">
      {stampers.map((r) => (
        <div key={r.person.id} role="alert" className="alert alert-warning alert-soft">
          <div>
            <div className="font-medium">{r.person.name} waves big PRs through</div>
            <p className="text-sm">
              Approves in {speed(r.minutes_per_100_lines)} per 100 lines (team median{" "}
              {speed(medians.minutes_per_100_lines)}
              ), {share(r.substantive_share)} of their comments are substantive (team {share(medians.substantive_share)}
              ), and {r.stamped_big_approvals} of {r.big_approvals} big approvals would be flagged as rubber stamps.{" "}
              {r.escapes > 0 && (
                <>
                  {r.escapes} of the {r.approved_merged} PRs they approved needed a revert or hotfix.{" "}
                </>
              )}
              <Link href={flagsHref("rubber_stamp", r.person.id)} className="link">
                See the flags
              </Link>
            </p>
          </div>
        </div>
      ))}

      <div className="grid gap-4 lg:grid-cols-2">
        <section className="card bg-base-100 shadow-sm">
          <div className="card-body">
            <h2 className="card-title text-base">Approval speed against substance</h2>
            <p className="text-sm opacity-70">
              Left is faster, lower says less of substance. Dashed lines are the team medians.
            </p>
            <SpeedVsDepthChart
              points={speedPoints}
              medianMinutes={medians.minutes_per_100_lines}
              medianSubstantive={
                medians.substantive_share === null ? null : Math.round(medians.substantive_share * 100)
              }
            />
          </div>
        </section>
        <section className="card bg-base-100 shadow-sm">
          <div className="card-body">
            <h2 className="card-title text-base">Escape rate</h2>
            <p className="text-sm opacity-70">
              Approved PRs that needed a revert or hotfix within {report.escape_window_days} days of merging.
            </p>
            <EscapeRateChart points={escapePoints} />
          </div>
        </section>
      </div>

      <div className="overflow-x-auto rounded-box bg-base-100">
        <table className="table">
          <thead>
            <tr>
              <th>Developer</th>
              <th className="text-right">Approvals</th>
              <th className="text-right">
                Time to approve
                <div className="font-normal opacity-60">per 100 lines</div>
              </th>
              <th className="text-right">
                Comments
                <div className="font-normal opacity-60">per 100 lines</div>
              </th>
              <th className="text-right">Substantive</th>
              <th className="text-right">Big PRs stamped</th>
              <th className="text-right">Escapes</th>
            </tr>
          </thead>
          <tbody>
            {report.people.map((r) => {
              const heavy = stampsBigPrs(r) ? "font-semibold text-error" : "";
              return (
                <tr key={r.person.id}>
                  <td className="whitespace-nowrap">
                    <Link href={`/people/${r.person.id}`} className="link link-hover">
                      {r.person.name}
                    </Link>
                  </td>
                  <td className="text-right">{r.approvals}</td>
                  <td className={`text-right ${heavy}`}>{speed(r.minutes_per_100_lines)}</td>
                  <td className="text-right">{r.comments_per_100_lines ?? "–"}</td>
                  <td className={`text-right ${heavy}`}>{share(r.substantive_share)}</td>
                  <td className={`text-right ${heavy}`}>
                    {r.stamped_big_approvals > 0 ? (
                      <Link href={flagsHref("rubber_stamp", r.person.id)} className="link">
                        {r.stamped_big_approvals} of {r.big_approvals}
                      </Link>
                    ) : (
                      `0 of ${r.big_approvals}`
                    )}
                  </td>
                  <td className="text-right">
                    {r.escapes > 0 ? (
                      <Link href={flagsHref("escape", r.person.id)} className="link">
                        {r.escapes} of {r.approved_merged} ({share(r.escape_rate)})
                      </Link>
                    ) : (
                      `0 of ${r.approved_merged}`
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
          <tfoot>
            <tr>
              <td>Team median</td>
              <td />
              <td className="text-right">{speed(medians.minutes_per_100_lines)}</td>
              <td className="text-right">{medians.comments_per_100_lines ?? "–"}</td>
              <td className="text-right">{share(medians.substantive_share)}</td>
              <td />
              <td className="text-right">{share(medians.escape_rate)}</td>
            </tr>
          </tfoot>
        </table>
      </div>
      <p className="text-xs opacity-60">
        Reviews from {formatDate(report.since)} to {formatDate(report.as_of)} ({report.weeks} weeks). Time to approve is
        from the PR opening to the reviewer&apos;s first approval. Big PRs are {report.big_pr_lines}+ changed lines; a
        stamp is an approval the rubber-stamp rule would flag. The manager&apos;s reviews are not counted.
      </p>
    </div>
  );
}
