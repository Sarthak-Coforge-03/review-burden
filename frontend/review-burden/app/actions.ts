"use server";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { VIEWER_COOKIE } from "@/lib/viewer";

/**
 * Demo-only viewer switch (no real auth). Expects `viewerId` and `role` fields and
 * redirects to that role's home page. The API, not this cookie, enforces access.
 */
export async function setViewer(formData: FormData): Promise<void> {
  const id = Number.parseInt(String(formData.get("viewerId") ?? ""), 10);
  if (!Number.isInteger(id) || id <= 0) return;
  (await cookies()).set(VIEWER_COOKIE, String(id), {
    path: "/",
    sameSite: "lax",
    maxAge: 60 * 60 * 24 * 30,
  });
  redirect(formData.get("role") === "dev" ? "/me" : "/");
}
