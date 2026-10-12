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

## Where things are

| Path | What |
|---|---|
| `app/layout.tsx` | Header (brand, nav, role switcher) and page frame |
| `app/*/page.tsx` | One folder per screen; most are placeholders until their feature branch lands |
| `components/viewer-bar.tsx` | Loads people and the current viewer, picks manager or developer nav |
| `components/role-switcher.tsx` | "Viewing as" dropdown |
| `components/nav-links.tsx` | Nav links with active state |
| `lib/api.ts`, `lib/viewer.ts` | Server-only API client and viewer cookie helpers |
| `lib/api-types.ts` | Named API types; `lib/openapi.json` and `lib/api-schema.d.ts` are generated |
