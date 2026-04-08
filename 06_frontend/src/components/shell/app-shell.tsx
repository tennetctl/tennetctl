"use client";

import * as React from "react";
import { usePathname } from "next/navigation";
import { Topbar } from "./topbar";
import { Sidebar } from "./sidebar";
import { findModuleByPath } from "./nav-config";

/**
 * Root app shell. Renders topbar + contextual sidebar + content.
 * Excludes itself from routes that want a bare layout (e.g. auth).
 */
const BARE_ROUTES = ["/sign-in", "/login"];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname() ?? "";
  const bare = BARE_ROUTES.some((r) => pathname.startsWith(r));

  if (bare) return <>{children}</>;

  const hasModule = !!findModuleByPath(pathname);

  return (
    <div className="flex min-h-screen flex-col bg-background text-foreground">
      <Topbar />
      <div className="flex flex-1">
        {hasModule && <Sidebar />}
        <main className="min-w-0 flex-1">{children}</main>
      </div>
    </div>
  );
}
