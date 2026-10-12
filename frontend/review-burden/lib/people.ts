import "server-only";

import { cache } from "react";

import { apiFetch } from "./api";
import type { Person } from "./api-types";
import { getViewerId } from "./viewer";

/**
 * Everyone on the team, or null if the API is unreachable. Fetched without `X-Viewer-Id`
 * so a developer viewer can still list the manager and switch back.
 */
export const loadPeople = cache(async (): Promise<Person[] | null> => {
  try {
    return await apiFetch<Person[]>("/api/people", { asViewer: false });
  } catch {
    return null;
  }
});

/** The person picked in the role switcher, falling back to the manager the same way the API does. */
export async function loadViewer(): Promise<{ people: Person[] | null; viewer: Person | null }> {
  const [people, viewerId] = await Promise.all([loadPeople(), getViewerId()]);
  const viewer =
    people?.find((p) => p.id === viewerId) ?? people?.find((p) => p.role === "manager") ?? null;
  return { people, viewer };
}
