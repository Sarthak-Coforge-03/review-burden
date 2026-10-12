"use server";

import { refresh } from "next/cache";

import { ApiError, apiFetch } from "@/lib/api";
import type { Flag, FlagStatus, FlagUpdate } from "@/lib/api-types";

const STATUSES: readonly FlagStatus[] = ["open", "acknowledged", "dismissed"];

export type TriageResult = { error: string } | null;

/**
 * Sets a flag's status as the current viewer. The API checks that the viewer is the manager
 * and that dismissing has a reason; this only rejects malformed input.
 */
export async function triageFlag(flagId: number, status: FlagStatus, dismissReason?: string): Promise<TriageResult> {
  if (!Number.isInteger(flagId) || flagId <= 0 || !STATUSES.includes(status)) {
    return { error: "Invalid request." };
  }
  if (status === "dismissed" && !dismissReason?.trim()) {
    return { error: "Give a reason for dismissing." };
  }

  const body: FlagUpdate = { status, dismiss_reason: status === "dismissed" ? dismissReason : null };
  try {
    await apiFetch<Flag>(`/api/flags/${flagId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch (error) {
    if (error instanceof ApiError && error.status === 403) return { error: "Only the manager can triage flags." };
    if (error instanceof ApiError && error.status === 404) return { error: "That flag no longer exists." };
    return { error: "Could not update the flag. Is the API running?" };
  }
  refresh();
  return null;
}
