"use server";

import { refresh } from "next/cache";

import { ApiError, apiFetch } from "@/lib/api";
import type { EngineRun, SettingsSaved } from "@/lib/api-types";
import { type FormValues, NUMBER_FIELDS, fieldLabel, fromFormValues, toFormValues } from "@/lib/settings-fields";

export type SettingsState = {
  /** Bumped on every result so the form remounts with `values`. */
  version: number;
  values: FormValues;
  /** The settings last loaded or saved; shown again after a re-run. */
  saved: FormValues;
  message: { kind: "success" | "error"; text: string } | null;
};

function describeRun(run: EngineRun): string {
  const parts = [`${run.created} new`, `${run.removed} removed`];
  if (run.kept_triaged) parts.push(`${run.kept_triaged} triaged kept`);
  return `Re-ran the rules: ${parts.join(", ")}. ${run.open_flags} open flags now.`;
}

type ValidationError = { loc: (string | number)[]; msg: string };

/** FastAPI's 422 body as one readable line per problem. */
function describeValidation(body: unknown): string {
  const detail = (body as { detail?: ValidationError[] } | null)?.detail;
  if (!Array.isArray(detail)) return "Some values are not valid.";
  return detail
    .map(({ loc, msg }) => {
      const text = msg.replace(/^Value error, /, "");
      const field = loc.length > 1 ? String(loc[1]) : null;
      return field ? `${fieldLabel(field)}: ${text}` : text.charAt(0).toUpperCase() + text.slice(1);
    })
    .join(" ");
}

function failure(error: unknown): string {
  if (error instanceof ApiError && error.status === 403) return "Only the manager can change settings.";
  if (error instanceof ApiError && error.status === 422) return describeValidation(error.body);
  return "Could not reach the API. Is it running?";
}

/** Save, reset or re-run, depending on which button submitted the form. */
export async function settingsAction(previous: SettingsState, formData: FormData): Promise<SettingsState> {
  const version = previous.version + 1;
  const intent = formData.get("intent");
  const submitted = Object.fromEntries(
    ["stock_phrases", ...NUMBER_FIELDS.map((f) => f.key)].map((key) => [key, String(formData.get(key) ?? "")]),
  ) as FormValues;

  try {
    if (intent === "rerun") {
      const run = await apiFetch<EngineRun>("/api/settings/run-engine", { method: "POST" });
      refresh();
      return { ...previous, version, values: previous.saved, message: { kind: "success", text: describeRun(run) } };
    }
    const saved =
      intent === "reset"
        ? await apiFetch<SettingsSaved>("/api/settings", { method: "DELETE" })
        : await apiFetch<SettingsSaved>("/api/settings", {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(fromFormValues(submitted)),
          });
    refresh();
    const done = intent === "reset" ? "Back to the defaults." : "Saved.";
    const values = toFormValues(saved.values);
    const text = `${done} ${describeRun(saved.engine)}`;
    return { version, values, saved: values, message: { kind: "success", text } };
  } catch (error) {
    const values = intent === "save" ? submitted : previous.saved;
    return { ...previous, version, values, message: { kind: "error", text: failure(error) } };
  }
}
