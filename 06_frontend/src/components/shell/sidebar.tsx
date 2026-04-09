"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { findModuleByPath } from "./nav-config";
import { useSidebar } from "./sidebar-context";
import { cn } from "@/lib/cn";

export function Sidebar() {
  const pathname = usePathname() ?? "";
  const mod = findModuleByPath(pathname);
  const { open, close } = useSidebar();

  if (!mod) return null;

  return (
    <>
      {/* Desktop sidebar — always visible ≥ md */}
      <aside className="sticky top-12 hidden h-[calc(100vh-3rem)] w-64 shrink-0 flex-col border-r border-border bg-surface md:flex">
        <SidebarContent mod={mod} pathname={pathname} />
      </aside>

      {/* Mobile drawer — slides in from left, overlay controlled by SidebarContext */}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-40 flex w-72 flex-col border-r border-border bg-surface shadow-lg transition-transform duration-200 md:hidden",
          open ? "translate-x-0" : "-translate-x-full"
        )}
        aria-modal={open}
        role="dialog"
        aria-label={`${mod.label} navigation`}
      >
        {/* Push content below the topbar */}
        <div className="h-12 shrink-0 border-b border-border" />
        <SidebarContent mod={mod} pathname={pathname} onNavigate={close} />
      </aside>
    </>
  );
}

function SidebarContent({
  mod,
  pathname,
  onNavigate,
}: {
  mod: NonNullable<ReturnType<typeof findModuleByPath>>;
  pathname: string;
  onNavigate?: () => void;
}) {
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      {/* Module identity header */}
      <div className="flex items-center gap-3 border-b border-border px-4 py-3.5">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md border border-border bg-surface-2">
          <mod.icon className="h-4 w-4 text-foreground" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5">
            <span className="text-sm font-semibold text-foreground">{mod.label}</span>
            <span className="rounded-sm bg-surface-3 px-1 py-px font-mono text-[9px] text-foreground-subtle">
              {mod.number}
            </span>
          </div>
          <p className="truncate text-[11px] text-foreground-muted">{mod.description}</p>
        </div>
      </div>

      {/* Scrollable nav groups */}
      <nav className="flex-1 overflow-y-auto py-2" aria-label={`${mod.label} navigation`}>
        {mod.groups.map((group) => (
          <div key={group.label} className="mb-1">
            <div className="px-4 pb-1 pt-3">
              <span className="text-[10px] font-semibold uppercase tracking-widest text-foreground-subtle">
                {group.label}
              </span>
            </div>
            <ul className="space-y-px px-2">
              {group.items.map((item) => {
                const isActive =
                  pathname === item.href ||
                  (item.href !== mod.href && pathname.startsWith(`${item.href}/`));
                const Icon = item.icon;
                return (
                  <li key={item.href}>
                    <Link
                      href={item.href}
                      onClick={onNavigate}
                      className={cn(
                        "group flex items-center gap-2.5 rounded-md px-2.5 py-2 text-[13px] transition-colors",
                        isActive
                          ? "bg-surface-3 font-medium text-foreground"
                          : "text-foreground-muted hover:bg-surface-2 hover:text-foreground"
                      )}
                      aria-current={isActive ? "page" : undefined}
                    >
                      <Icon
                        className={cn(
                          "h-4 w-4 shrink-0 transition-colors",
                          isActive
                            ? "text-foreground"
                            : "text-foreground-subtle group-hover:text-foreground-muted"
                        )}
                      />
                      <span className="flex-1 truncate">{item.label}</span>
                      {item.badge && (
                        <span className="rounded-sm border border-border bg-surface-2 px-1 py-px font-mono text-[9px] text-foreground-subtle">
                          {item.badge}
                        </span>
                      )}
                      {isActive && (
                        <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-foreground" />
                      )}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </nav>

      {/* Scope footer */}
      <div className="border-t border-border bg-surface-2 px-4 py-3">
        <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-widest text-foreground-subtle">
          Active Scope
        </p>
        <div className="space-y-1">
          <div className="flex items-center justify-between">
            <span className="text-[11px] text-foreground-muted">Org</span>
            <span className="max-w-[120px] truncate text-right font-mono text-[11px] text-foreground">
              tennetctl
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-[11px] text-foreground-muted">Workspace</span>
            <span className="max-w-[120px] truncate text-right font-mono text-[11px] text-foreground">
              default
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
