import Link from "next/link";
import { notFound } from "next/navigation";

import { ApiError, apiFetch } from "@/lib/api";
import type { Flag, PendingReview, PersonProfile, RoleSummary } from "@/lib/api-types";
import { describePattern, duration, formatDate, percent, RULE_LABELS } from "@/lib/flag-format";
import { loadViewer } from "@/lib/people";

import { FlagTable } from "./flag-table";

/**
 * A person's profile: activity, repeat patterns, flags by role, review debt and their flags.
 * Reads the viewer cookie, so render it inside `<Suspense>`.
 */
export async function PersonProfileView({ personId }: { personId: number }) {
  const { people, viewer } = await loadViewer();
  let profile: PersonProfile;
  let flags: Flag[];
  try {
    [profile, flags] = await Promise.all([
      apiFetch<PersonProfile>(`/api/people/${personId}/profile`),
      apiFetch<Flag[]>(`/api/flags?person_id=${personId}`),
    ]);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) notFound();
    if (error instanceof ApiError && error.status === 403) {
      return <div className="alert">You can only see your own profile.</div>;
    }
    return <div className="alert alert-error">Could not load this profile. Is the API running?</div>;
  }

  const isManager = viewer?.role === "manager";
  const isSelf = viewer?.id === personId;
  const name = isSelf ? "you" : profile.person.name.split(" ")[0];
  const { activity } = profile;
  const stale = profile.review_debt.filter((r) => r.stale).length;
  const flagsHref = (rule: string) => (isManager ? `/flags?person=${personId}&rule=${rule}&status=all` : `/flags?rule=${rule}&status=all`);

  return (
    <div className="space-y-6">
      <div className="stats stats-vertical w-full bg-base-100 shadow-sm md:stats-horizontal">
        <div className="stat">
          <div className="stat-title">Open flags</div>
          <div className="stat-value">{profile.as_author.open + profile.as_reviewer.open}</div>
          <div className="stat-desc">not yet acknowledged</div>
        </div>
        <div className="stat">
          <div className="stat-title">Reviews, last {activity.window_days} days</div>
          <div className={`stat-value ${activity.over_median_multiple ? "text-error" : ""}`}>
            {activity.reviews_given}
          </div>
          <div className="stat-desc">
            {percent(activity.share)} of the team&apos;s {activity.team_reviews}; median {activity.team_median}
          </div>
        </div>
        <div className="stat">
          <div className="stat-title">Waiting on {name}</div>
          <div className={`stat-value ${stale ? "text-error" : ""}`}>{profile.review_debt.length}</div>
          <div className="stat-desc">{stale ? `${stale} past the stale threshold` : "review requests, none stale"}</div>
        </div>
        <div className="stat">
          <div className="stat-title">PRs opened, last {activity.window_days} days</div>
          <div className="stat-value">{activity.prs_opened}</div>
          <div className="stat-desc">as author</div>
        </div>
      </div>

      {profile.patterns.length > 0 && (
        <section className="space-y-2">
          <h2 className="text-lg font-semibold">Repeat patterns</h2>
          {profile.patterns.map((pattern) => (
            <div key={`${pattern.rule_key}-${pattern.role}`} role="alert" className="alert alert-warning alert-soft">
              <div>
                <div className="font-medium">{describePattern(pattern)}</div>
                <div className="text-sm">
                  {pattern.pull_requests.map((pr) => `#${pr.id} ${pr.title}`).join(" · ")}
                </div>
              </div>
            </div>
          ))}
        </section>
      )}

      <div className="grid gap-4 md:grid-cols-2">
        <RoleCard title="As author" summary={profile.as_author} flagsHref={flagsHref} />
        <RoleCard title="As reviewer" summary={profile.as_reviewer} flagsHref={flagsHref} />
      </div>

      <section className="space-y-2">
        <h2 className="text-lg font-semibold">Review requests waiting on {name}</h2>
        <ReviewDebt requests={profile.review_debt} />
      </section>

      <section className="space-y-2">
        <h2 className="text-lg font-semibold">Flags</h2>
        <FlagTable
          flags={flags}
          people={people}
          canTriage={isManager}
          emptyMessage={`No flags for ${name}. Nothing to look at.`}
        />
      </section>
    </div>
  );
}

function RoleCard({
  title,
  summary,
  flagsHref,
}: {
  title: string;
  summary: RoleSummary;
  flagsHref: (rule: string) => string;
}) {
  return (
    <section className="card bg-base-100 shadow-sm">
      <div className="card-body gap-3">
        <h2 className="card-title text-base">
          {title}
          {summary.open > 0 && <span className="badge badge-warning badge-sm">{summary.open} open</span>}
        </h2>
        {summary.flags.length === 0 ? (
          <p className="text-sm opacity-70">No flags.</p>
        ) : (
          <ul className="space-y-1">
            {summary.flags.map(({ rule_key, count }) => (
              <li key={rule_key} className="flex items-center justify-between gap-2 text-sm">
                <Link href={flagsHref(rule_key)} className="link link-hover">
                  {RULE_LABELS[rule_key]}
                </Link>
                <span className="badge badge-sm">{count}</span>
              </li>
            ))}
          </ul>
        )}
        <p className="text-xs opacity-60">Dismissed flags are not counted.</p>
      </div>
    </section>
  );
}

function ReviewDebt({ requests }: { requests: PendingReview[] }) {
  if (requests.length === 0) {
    return <div className="rounded-box bg-base-100 p-6 text-center opacity-70">Nothing waiting. All caught up.</div>;
  }
  return (
    <div className="overflow-x-auto rounded-box bg-base-100">
      <table className="table">
        <thead>
          <tr>
            <th>Pull request</th>
            <th>Requested</th>
            <th>Waiting</th>
          </tr>
        </thead>
        <tbody>
          {requests.map((r) => (
            <tr key={r.pull_request.id}>
              <td>
                <span className="font-mono text-xs opacity-60">#{r.pull_request.id}</span> {r.pull_request.title}
              </td>
              <td className="whitespace-nowrap">{formatDate(r.requested_at)}</td>
              <td className="whitespace-nowrap">
                {duration(r.waiting_hours * 3600)}
                {r.stale && <span className="badge badge-error badge-sm ml-2">stale</span>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
