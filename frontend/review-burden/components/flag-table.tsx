import type { Flag, FlagStatus, Person } from "@/lib/api-types";
import { describeEvidence, formatDate, RULE_LABELS, STATUS_LABELS } from "@/lib/flag-format";

import { TriageControls } from "./triage-controls";

const STATUS_BADGES: Record<FlagStatus, string> = {
  open: "badge-warning",
  acknowledged: "badge-info",
  dismissed: "badge-ghost",
};

type FlagTableProps = {
  flags: Flag[];
  /** Used to name people mentioned in evidence (pending reviewers, overloaded reviewers). */
  people: Person[] | null;
  canTriage: boolean;
  emptyMessage?: string;
};

export function FlagTable({ flags, people, canTriage, emptyMessage = "No flags." }: FlagTableProps) {
  if (flags.length === 0) {
    return <div className="rounded-box bg-base-100 p-8 text-center opacity-70">{emptyMessage}</div>;
  }

  const names = new Map(people?.map((p) => [p.id, p.name]));
  const nameOf = (id: number) => names.get(id) ?? `Person ${id}`;

  return (
    <div className="overflow-x-auto rounded-box bg-base-100">
      <table className="table">
        <thead>
          <tr>
            <th>Flag</th>
            <th>Pull request</th>
            <th>Evidence</th>
            <th>Status</th>
            {canTriage && (
              <th className="w-px">
                <span className="sr-only">Actions</span>
              </th>
            )}
          </tr>
        </thead>
        <tbody>
          {flags.map((flag) => (
            <FlagRow key={flag.id} flag={flag} evidence={describeEvidence(flag, nameOf)} canTriage={canTriage} />
          ))}
        </tbody>
      </table>
    </div>
  );
}

function FlagRow({ flag, evidence, canTriage }: { flag: Flag; evidence: string; canTriage: boolean }) {
  const pr = flag.pull_request;
  return (
    <tr className="[&>td]:align-top">
      <td className="min-w-44">
        <div className="font-medium">{RULE_LABELS[flag.rule_key]}</div>
        <div className="text-sm">
          {flag.person ? flag.person.name : "Whole team"}
          {flag.role && <span className="opacity-60"> as {flag.role}</span>}
        </div>
        <div className="text-xs opacity-60">{formatDate(flag.occurred_at)}</div>
      </td>
      <td className="w-52">
        {pr ? (
          <>
            <div className="font-mono text-xs opacity-60">#{pr.id}</div>
            <div className="line-clamp-2 text-sm">{pr.title}</div>
          </>
        ) : (
          <span className="text-sm opacity-60">None</span>
        )}
      </td>
      <td className="min-w-64">{evidence}</td>
      <td className="w-40">
        <span className={`badge badge-sm ${STATUS_BADGES[flag.status]}`}>{STATUS_LABELS[flag.status]}</span>
        {flag.dismiss_reason && <p className="mt-1 text-xs opacity-70">{flag.dismiss_reason}</p>}
        {flag.note && <p className="mt-1 text-xs italic opacity-70">Note: {flag.note}</p>}
      </td>
      {canTriage && (
        <td className="w-px">
          <TriageControls
            flagId={flag.id}
            status={flag.status}
            label={`${RULE_LABELS[flag.rule_key]}${flag.person ? ` · ${flag.person.name}` : ""}${pr ? ` · #${pr.id}` : ""}`}
          />
        </td>
      )}
    </tr>
  );
}
