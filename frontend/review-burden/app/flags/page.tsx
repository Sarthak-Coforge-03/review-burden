import Form from "next/form";
import Link from "next/link";
import { Suspense } from "react";

import { apiFetch } from "@/lib/api";
import type { Flag, FlagStatus, RuleKey } from "@/lib/api-types";
import { FlagTable } from "@/components/flag-table";
import { RULE_LABELS, STATUS_LABELS } from "@/lib/flag-format";
import { loadViewer } from "@/lib/people";

type StatusTab = FlagStatus | "all";
type Filters = { status: StatusTab; rule?: RuleKey; person?: number };
type SearchParams = Record<string, string | string[] | undefined>;

const TABS: StatusTab[] = ["open", "acknowledged", "dismissed", "all"];

function first(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

function parseFilters(params: SearchParams): Filters {
  const status = first(params.status);
  const rule = first(params.rule);
  const person = Number.parseInt(first(params.person) ?? "", 10);
  return {
    status: TABS.includes(status as StatusTab) ? (status as StatusTab) : "open",
    rule: rule && rule in RULE_LABELS ? (rule as RuleKey) : undefined,
    person: person > 0 ? person : undefined,
  };
}

function flagsHref({ status, rule, person }: Filters): string {
  const query = new URLSearchParams();
  if (status !== "open") query.set("status", status);
  if (rule) query.set("rule", rule);
  if (person) query.set("person", String(person));
  const qs = query.toString();
  return qs ? `/flags?${qs}` : "/flags";
}

export default function FlagsPage({ searchParams }: PageProps<"/flags">) {
  return (
    <section className="space-y-4">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold">Flags</h1>
        <p className="max-w-2xl opacity-70">
          Every flag comes from a fixed rule and shows the evidence that triggered it. Acknowledge what needs
          follow-up; dismiss with a reason what turned out fine.
        </p>
      </div>
      <Suspense fallback={<div className="skeleton h-96 w-full" />}>
        <FlagInbox searchParams={searchParams} />
      </Suspense>
    </section>
  );
}

async function FlagInbox({ searchParams }: { searchParams: Promise<SearchParams> }) {
  const [{ people, viewer }, params] = await Promise.all([loadViewer(), searchParams]);
  const isManager = viewer?.role === "manager";
  const filters = parseFilters(params);
  if (!isManager) filters.person = undefined;

  const query = new URLSearchParams();
  if (filters.rule) query.set("rule_key", filters.rule);
  if (filters.person) query.set("person_id", String(filters.person));

  let flags: Flag[];
  try {
    flags = await apiFetch<Flag[]>(`/api/flags?${query}`);
  } catch {
    return <div className="alert alert-error">Could not load flags. Is the API running?</div>;
  }

  const counts: Record<StatusTab, number> = { open: 0, acknowledged: 0, dismissed: 0, all: flags.length };
  for (const flag of flags) counts[flag.status] += 1;
  const shown = filters.status === "all" ? flags : flags.filter((f) => f.status === filters.status);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div role="tablist" className="tabs tabs-box">
          {TABS.map((tab) => (
            <Link
              key={tab}
              role="tab"
              href={flagsHref({ ...filters, status: tab })}
              className={`tab gap-2 ${tab === filters.status ? "tab-active" : ""}`}
            >
              {tab === "all" ? "All" : STATUS_LABELS[tab]}
              <span className="badge badge-sm">{counts[tab]}</span>
            </Link>
          ))}
        </div>

        <Form action="" className="flex flex-wrap items-end gap-2">
          {filters.status !== "open" && <input type="hidden" name="status" value={filters.status} />}
          <select name="rule" defaultValue={filters.rule ?? ""} className="select select-sm w-56" aria-label="Rule">
            <option value="">All rules</option>
            {Object.entries(RULE_LABELS).map(([key, label]) => (
              <option key={key} value={key}>
                {label}
              </option>
            ))}
          </select>
          {isManager && (
            <select
              name="person"
              defaultValue={filters.person ?? ""}
              className="select select-sm w-44"
              aria-label="Person"
            >
              <option value="">Everyone</option>
              {people?.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          )}
          <button type="submit" className="btn btn-sm">
            Filter
          </button>
          {(filters.rule || filters.person) && (
            <Link href={flagsHref({ status: filters.status })} className="btn btn-sm btn-ghost">
              Clear
            </Link>
          )}
        </Form>
      </div>

      <FlagTable flags={shown} people={people} canTriage={isManager} emptyMessage="No flags match these filters." />
    </div>
  );
}

