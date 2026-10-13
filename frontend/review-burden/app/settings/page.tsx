import { Suspense } from "react";

import { SettingsForm } from "@/components/settings-form";
import { ApiError, apiFetch } from "@/lib/api";
import type { SettingsOut } from "@/lib/api-types";
import { loadPeople } from "@/lib/people";
import { toFormValues } from "@/lib/settings-fields";

export default function SettingsPage() {
  return (
    <section className="space-y-4">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold">Rules and weights</h1>
        <p className="max-w-2xl opacity-70">
          The thresholds every rule uses and the health score weights. Saving re-runs the rules at once: new problems
          become open flags, open flags that no longer fire are removed, and acknowledged or dismissed flags are kept.
        </p>
      </div>
      <Suspense fallback={<div className="skeleton h-96 w-full" />}>
        <Settings />
      </Suspense>
    </section>
  );
}

async function Settings() {
  let settings: SettingsOut;
  try {
    settings = await apiFetch<SettingsOut>("/api/settings");
  } catch (error) {
    if (error instanceof ApiError && error.status === 403) {
      return <div className="alert">Only the manager can change the rules.</div>;
    }
    return <div className="alert alert-error">Could not load settings. Is the API running?</div>;
  }
  const developers = ((await loadPeople()) ?? []).filter((p) => p.role === "dev");
  return (
    <SettingsForm
      values={toFormValues(settings.values)}
      defaults={toFormValues(settings.defaults)}
      developers={developers}
    />
  );
}
