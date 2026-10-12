import { Suspense } from "react";

import { PersonProfileView } from "@/components/person-profile";
import { loadViewer } from "@/lib/people";

export default function MePage() {
  return (
    <section className="space-y-4">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold">My review debt and flags</h1>
        <p className="max-w-2xl opacity-70">
          Reviews waiting on you, your share of the team&apos;s review work, and your flags with the same evidence
          your manager sees.
        </p>
      </div>
      <Suspense fallback={<div className="skeleton h-96 w-full" />}>
        <MyProfile />
      </Suspense>
    </section>
  );
}

async function MyProfile() {
  const { viewer } = await loadViewer();
  if (!viewer) return <div className="alert alert-error">Could not load people. Is the API running?</div>;
  return <PersonProfileView personId={viewer.id} />;
}
