import "server-only";

import { cookies } from "next/headers";

export const VIEWER_COOKIE = "viewer_id";

/** The person id chosen in the role switcher, or null if none is set or the cookie is malformed. */
export async function getViewerId(): Promise<number | null> {
  const raw = (await cookies()).get(VIEWER_COOKIE)?.value;
  const id = raw ? Number.parseInt(raw, 10) : NaN;
  return Number.isInteger(id) && id > 0 ? id : null;
}
