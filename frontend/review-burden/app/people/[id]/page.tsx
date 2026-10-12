import Link from "next/link";
import { notFound } from "next/navigation";
import { Suspense } from "react";

import { PersonProfileView } from "@/components/person-profile";
import { loadPeople } from "@/lib/people";

export default function PersonPage({ params }: PageProps<"/people/[id]">) {
  return (
    <section className="space-y-4">
      <Link href="/people" className="link link-hover text-sm opacity-70">
        ← People
      </Link>
      <Suspense fallback={<div className="skeleton h-96 w-full" />}>
        <Person params={params} />
      </Suspense>
    </section>
  );
}

async function Person({ params }: { params: Promise<{ id: string }> }) {
  const id = Number.parseInt((await params).id, 10);
  if (!(id > 0)) notFound();
  const person = (await loadPeople())?.find((p) => p.id === id);

  return (
    <>
      <h1 className="text-2xl font-semibold">{person?.name ?? `Person ${id}`}</h1>
      <PersonProfileView personId={id} />
    </>
  );
}
