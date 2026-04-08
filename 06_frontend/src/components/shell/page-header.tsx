import * as React from "react";
import { cn } from "@/lib/cn";

interface PageHeaderProps {
  title: string;
  description?: string;
  breadcrumb?: string[];
  actions?: React.ReactNode;
  className?: string;
}

export function PageHeader({
  title,
  description,
  breadcrumb,
  actions,
  className,
}: PageHeaderProps) {
  return (
    <div
      className={cn(
        "border-b border-border bg-surface px-4 py-4 sm:px-6 sm:py-5",
        className
      )}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1 space-y-1">
          {breadcrumb && breadcrumb.length > 0 && (
            <nav
              className="flex items-center gap-1.5 text-[10px] font-medium uppercase tracking-wider text-foreground-subtle"
              aria-label="Breadcrumb"
            >
              {breadcrumb.map((crumb, i) => (
                <React.Fragment key={i}>
                  {i > 0 && <span>/</span>}
                  <span>{crumb}</span>
                </React.Fragment>
              ))}
            </nav>
          )}
          <h1 className="truncate text-lg font-semibold tracking-tight text-foreground sm:text-xl">
            {title}
          </h1>
          {description && (
            <p className="text-xs text-foreground-muted">{description}</p>
          )}
        </div>
        {actions && (
          <div className="flex shrink-0 items-center gap-2">{actions}</div>
        )}
      </div>
    </div>
  );
}

export function PageBody({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return <div className={cn("p-4 sm:p-6", className)}>{children}</div>;
}
