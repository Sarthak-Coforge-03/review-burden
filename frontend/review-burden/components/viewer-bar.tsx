import { loadViewer } from "@/lib/people";

import { NavLinks, type NavItem } from "./nav-links";
import { RoleSwitcher } from "./role-switcher";

const MANAGER_NAV: NavItem[] = [
  { href: "/", label: "Overview" },
  { href: "/flags", label: "Flags" },
  { href: "/load", label: "Review load" },
  { href: "/quality", label: "Review quality" },
  { href: "/people", label: "People" },
  { href: "/settings", label: "Settings" },
];

const DEV_NAV: NavItem[] = [{ href: "/me", label: "My review debt and flags" }];

/** Nav and role switcher for the current viewer. Defaults to the manager when no viewer is chosen. */
export async function ViewerBar() {
  const { people, viewer: current } = await loadViewer();
  const nav = current?.role === "dev" ? DEV_NAV : MANAGER_NAV;

  return (
    <>
      <nav className="flex-1 min-w-0">
        <NavLinks items={nav} />
      </nav>
      <div className="flex-none">
        <RoleSwitcher people={people} currentId={current?.id ?? null} />
      </div>
    </>
  );
}

export function ViewerBarFallback() {
  return (
    <>
      <div className="flex-1">
        <div className="skeleton h-8 w-96" />
      </div>
      <div className="flex-none">
        <div className="skeleton h-8 w-64" />
      </div>
    </>
  );
}
