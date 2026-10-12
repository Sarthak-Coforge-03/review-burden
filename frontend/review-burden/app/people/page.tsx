import Link from "next/link";
import { Suspense } from "react";

import { ApiError, apiFetch } from "@/lib/api";
import type { PersonProfile } from "@/lib/api-types";
import { describePattern, percent } from "@/lib/flag-format";

export default function PeoplePage() {
  return (
    <section className="space-y-4">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold">People</h1>
        <p className="max-w-2xl opacity-70">
          Each developer&apos;s flags as author and as reviewer, repeat patterns, and how much review work is
          waiting on them. Open a person for the evidence.
        </p>
      </div>
      <Suspense fallback={<div className="skeleton h-96 w-full" />}>
        <PeopleGrid />
      </Suspense>
    </section>
  );
}

async function PeopleGrid() {
  let profiles: PersonProfile[];
  try {
    profiles = await apiFetch<PersonProfile[]>("/api/people/profiles");
  } catch (error) {
    if (error instanceof ApiError && error.status === 403) {
      return (
        <div className="alert">
          Only the manager sees everyone.{" "}
          <Link href="/me" className="link">
            See your own page
          </Link>
          .
        </div>
      );
    }
    return <div className="alert alert-error">Could not load people. Is the API running?</div>;
  }

  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
      {profiles.map((profile) => (
        <PersonCard key={profile.person.id} profile={profile} />
      ))}
    </div>
  );
}

function PersonCard({ profile }: { profile: PersonProfile }) {
  const { person, as_author, as_reviewer, patterns, review_debt, activity } = profile;
  const open = as_author.open + as_reviewer.open;
  const stale = review_debt.filter((r) => r.stale).length;
  const heavy = activity.over_median_multiple;

  return (
    <Link
      href={`/people/${person.id}`}
      className="card bg-base-100 shadow-sm transition-shadow hover:shadow-md focus-visible:outline"
    >
      <div className="card-body gap-3">
        <div className="flex items-center justify-between gap-2">
          <h2 className="card-title text-base">{person.name}</h2>
          {open > 0 ? (
            <span className="badge badge-warning">{open} open</span>
          ) : (
            <span className="badge badge-ghost">no open flags</span>
          )}
        </div>

        <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
          <dt className="opacity-60">Flags as author</dt>
          <dd className="text-right">{as_author.flags.reduce((n, c) => n + c.count, 0)}</dd>
          <dt className="opacity-60">Flags as reviewer</dt>
          <dd className="text-right">{as_reviewer.flags.reduce((n, c) => n + c.count, 0)}</dd>
          <dt className="opacity-60">Reviews, {activity.window_days} days</dt>
          <dd className={`text-right ${heavy ? "font-semibold text-error" : ""}`}>
            {activity.reviews_given} ({percent(activity.share)})
          </dd>
          <dt className="opacity-60">Waiting on them</dt>
          <dd className={`text-right ${stale ? "font-semibold text-error" : ""}`}>
            {review_debt.length}
            {stale > 0 && ` (${stale} stale)`}
          </dd>
        </dl>

        {patterns.map((pattern) => (
          <div key={`${pattern.rule_key}-${pattern.role}`} className="alert alert-warning alert-soft py-2 text-sm">
            {describePattern(pattern)}
          </div>
        ))}
      </div>
    </Link>
  );
}
