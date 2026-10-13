# Frontend

Next.js 16 (App Router) with Tailwind 4 + DaisyUI 5 and Recharts. See the root README for running everything with Docker.

```bash
npm install
npm run dev     # http://localhost:3000, API expected on http://localhost:8000
npm run build   # production build (standalone output, used by the Dockerfile)
npm run lint
npm run gen:api # after changing the API: re-export lib/openapi.json and regenerate lib/api-schema.d.ts (needs uv)
```

## API types

Types for API responses and requests are generated from the backend's OpenAPI schema, never written by hand. Import them from `lib/api-types.ts` (`Person`, `Flag`, `FlagUpdate`, ...). Both generated files are committed so builds don't need the backend; a backend test fails when `lib/openapi.json` is out of date.

## How data is fetched

- Pages are Server Components and call the API through `apiFetch` in `lib/api.ts`. It runs on the server only and adds `X-Viewer-Id` from the `viewer_id` cookie.
- `cacheComponents` is enabled, so anything that reads cookies or fetches per-request data must render inside a `<Suspense>` boundary (see `components/viewer-bar.tsx`), otherwise `next build` fails.
- The role switcher changes the viewer through the `setViewer` Server Action in `app/actions.ts`.
- Mutations go through Server Actions that call the API with `apiFetch` and then `refresh()` the page (see `app/flags/actions.ts`). The API enforces who may do what; the UI only hides controls.

## Where things are

| Path | What |
|---|---|
| `app/layout.tsx` | Header (brand, nav, role switcher) and page frame |
| `app/*/page.tsx` | One folder per screen |
| `app/page.tsx`, `components/health-trend-chart.tsx` | Team overview (manager only): health score and its five parts, KPI tiles, weekly score trend |
| `app/flags/` | Flag inbox: status tabs, rule/person filters (URL search params), triage via the `triageFlag` Server Action |
| `app/people/`, `app/people/[id]/` | Developer cards (manager only) and one person's profile |
| `app/load/`, `components/load-charts.tsx` | Review load (manager only): weekly and 28-day charts (Recharts, client component), per-person table |
| `app/quality/`, `components/quality-charts.tsx` | Review quality (manager only): approval speed vs substance scatter, escape-rate bars, per-person table linking to their flags |
| `app/settings/`, `components/settings-form.tsx`, `lib/settings-fields.ts` | Rule thresholds and health score weights (manager only): save, reset to defaults, re-run the rules, reset the demo data, all via the `settingsAction` Server Action |
| `components/chart-theme.ts` | Colors, axis and tooltip styles shared by the charts |
| `components/person-profile.tsx` | Profile view shared by `/people/[id]` and `/me`: activity, patterns, flags by role, review debt, flags |
| `components/flag-table.tsx`, `components/triage-controls.tsx` | Flags table and acknowledge/dismiss/reopen buttons, shared by the flag inbox and profiles |
| `components/viewer-bar.tsx` | Loads people and the current viewer, picks manager or developer nav |
| `components/role-switcher.tsx` | "Viewing as" dropdown |
| `components/nav-links.tsx` | Nav links with active state |
| `lib/api.ts`, `lib/viewer.ts` | Server-only API client and viewer cookie helpers |
| `lib/people.ts` | Team roster and the current viewer (shared by the header and pages) |
| `lib/flag-format.ts` | Rule labels and plain-language evidence sentences |
| `lib/api-types.ts` | Named API types; `lib/openapi.json` and `lib/api-schema.d.ts` are generated |
