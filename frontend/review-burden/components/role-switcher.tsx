"use client";

import { useTransition } from "react";

import { setViewer } from "@/app/actions";
import type { Person } from "@/lib/api-types";

type RoleSwitcherProps = {
  people: Person[] | null;
  currentId: number | null;
};

export function RoleSwitcher({ people, currentId }: RoleSwitcherProps) {
  const [pending, startTransition] = useTransition();

  if (people === null || people.length === 0) {
    return (
      <span className="badge badge-ghost" title="The role switcher lists people from GET /api/people">
        {people === null ? "API unavailable" : "No people yet, run the seed"}
      </span>
    );
  }

  const managers = people.filter((p) => p.role === "manager");
  const devs = people.filter((p) => p.role === "dev");

  function onChange(event: React.ChangeEvent<HTMLSelectElement>) {
    const person = people?.find((p) => String(p.id) === event.target.value);
    if (!person) return;
    const formData = new FormData();
    formData.set("viewerId", String(person.id));
    formData.set("role", person.role);
    startTransition(() => setViewer(formData));
  }

  return (
    <label className="flex items-center gap-2 text-sm">
      <span className="hidden xl:inline opacity-70 whitespace-nowrap">Viewing as</span>
      <select
        className="select select-sm w-44"
        value={currentId ?? ""}
        onChange={onChange}
        disabled={pending}
        aria-label="Switch viewer"
      >
        <optgroup label="Manager">
          {managers.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </optgroup>
        <optgroup label="Developer">
          {devs.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </optgroup>
      </select>
    </label>
  );
}
