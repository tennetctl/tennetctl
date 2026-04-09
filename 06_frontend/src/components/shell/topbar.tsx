"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { ChevronDown, LogOut, User as UserIcon, Loader2, Menu, X } from "lucide-react";
import { NAV_MODULES, findModuleByPath } from "./nav-config";
import { ThemeToggle } from "./theme-toggle";
import { useAuth } from "@/components/providers/auth-provider";
import { useSidebar } from "./sidebar-context";
import { cn } from "@/lib/cn";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Kbd } from "@/components/ui/kbd";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

export function Topbar() {
  const pathname = usePathname();
  const active = findModuleByPath(pathname ?? "");
  const { open, toggle } = useSidebar();
  const hasModule = !!active;

  return (
    <header className="sticky top-0 z-40 h-12 border-b border-border bg-surface/80 backdrop-blur-md">
      <div className="flex h-full items-center gap-2 px-3">
        {/* Hamburger — only on mobile when a module sidebar exists */}
        {hasModule && (
          <Button
            variant="ghost"
            size="icon"
            className="md:hidden"
            onClick={toggle}
            aria-label={open ? "Close menu" : "Open menu"}
          >
            {open ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
          </Button>
        )}

        {/* Brand */}
        <Link
          href="/"
          className="flex items-center gap-2 pr-2 font-semibold tracking-tight text-foreground"
        >
          <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-sm bg-foreground text-background">
            <span className="text-[11px] font-black">T</span>
          </div>
          <span className="hidden text-sm sm:inline">tennetctl</span>
          <Badge variant="outline" className="ml-1 hidden sm:inline-flex">
            S-Control
          </Badge>
        </Link>

        <div className="mx-1 hidden h-5 w-px bg-border sm:block" />

        {/* Module tabs — icons only on mobile, icons+labels on desktop */}
        <nav className="flex items-center gap-0.5" aria-label="Modules">
          {NAV_MODULES.map((m) => {
            const isActive = active?.key === m.key;
            const Icon = m.icon;
            return (
              <Link
                key={m.key}
                href={m.href}
                className={cn(
                  "group relative flex h-8 items-center gap-2 rounded-md px-2 text-xs font-medium transition-colors sm:px-3",
                  isActive
                    ? "bg-surface-3 text-foreground"
                    : "text-foreground-muted hover:bg-surface-2 hover:text-foreground"
                )}
                aria-current={isActive ? "page" : undefined}
                title={m.label}
              >
                <Icon className="h-3.5 w-3.5" />
                <span className="hidden sm:inline">{m.label}</span>
                <span className="hidden font-mono text-[9px] text-foreground-subtle sm:inline">
                  {m.number}
                </span>
              </Link>
            );
          })}
        </nav>

        {/* Right side */}
        <div className="ml-auto flex items-center gap-1">
          {/* Search hint — desktop only */}
          <div className="hidden items-center gap-1.5 rounded-md border border-border bg-surface-2 px-2 py-1 text-xs text-foreground-subtle lg:flex">
            <span>Search</span>
            <Kbd>⌘</Kbd>
            <Kbd>K</Kbd>
          </div>
          <ThemeToggle />
          <UserMenu />
        </div>
      </div>
    </header>
  );
}

function UserMenu() {
  const auth = useAuth();
  const router = useRouter();

  if (auth.status === "loading") {
    return (
      <Button variant="ghost" size="icon" disabled>
        <Loader2 className="h-3.5 w-3.5 animate-spin" />
      </Button>
    );
  }

  if (auth.status === "unauthenticated") {
    return (
      <Button
        variant="ghost"
        size="sm"
        className="gap-2 text-foreground-muted"
        onClick={() => router.push("/iam")}
      >
        <div className="flex h-5 w-5 items-center justify-center rounded-full border border-border">
          <UserIcon className="h-3 w-3" />
        </div>
        <span className="hidden sm:inline text-xs">Sign in</span>
      </Button>
    );
  }

  const displayName = auth.me.username ?? auth.me.email ?? auth.me.user_id.slice(0, 8);

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="sm" className="gap-1.5 px-2">
          <div className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-foreground text-background">
            <UserIcon className="h-3 w-3" />
          </div>
          <span className="hidden max-w-[120px] truncate text-xs sm:inline">{displayName}</span>
          <ChevronDown className="h-3 w-3 opacity-60" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="min-w-[200px]">
        <DropdownMenuLabel className="font-normal">
          <div className="flex flex-col gap-0.5">
            <span className="text-xs font-semibold text-foreground">{displayName}</span>
            {auth.me.email && (
              <span className="text-[11px] text-foreground-muted">{auth.me.email}</span>
            )}
            <span className="font-mono text-[10px] text-foreground-subtle">
              session {auth.sessionId.slice(0, 8)}…
            </span>
          </div>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem
          className="text-[color:var(--danger)] focus:text-[color:var(--danger)]"
          onClick={async () => {
            await auth.signOut();
            router.push("/iam");
          }}
        >
          <LogOut /> Sign out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
