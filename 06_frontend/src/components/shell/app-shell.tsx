"use client";

import * as React from "react";
import { usePathname } from "next/navigation";
import { Topbar } from "./topbar";
import { Sidebar } from "./sidebar";
import { SidebarProvider, useSidebar } from "./sidebar-context";
import { findModuleByPath } from "./nav-config";

const BARE_ROUTES = ["/sign-in", "/login"];

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <SidebarProvider>
      <AppShellInner>{children}</AppShellInner>
    </SidebarProvider>
  );
}

function AppShellInner({ children }: { children: React.ReactNode }) {
  const pathname = usePathname() ?? "";
  const bare = BARE_ROUTES.some((r) => pathname.startsWith(r));
  const { open, close } = useSidebar();

  if (bare) return <>{children}</>;

  const hasModule = !!findModuleByPath(pathname);

  return (
    <div className="flex min-h-screen flex-col bg-background text-foreground">
      <Topbar />
      <div className="flex flex-1">
        {hasModule && <Sidebar />}
        {/* Mobile drawer backdrop */}
        {hasModule && open && (
          <div
            className="fixed inset-0 z-30 bg-black/40 md:hidden"
            onClick={close}
            aria-hidden="true"
          />
        )}
        <main className="min-w-0 flex-1">{children}</main>
      </div>
    </div>
  );
}
