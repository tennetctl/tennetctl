import * as React from "react";
import { cn } from "@/lib/cn";

interface EmptyStateProps extends React.HTMLAttributes<HTMLDivElement> {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  action?: React.ReactNode;
}

export function EmptyState({
  icon,
  title,
  description,
  action,
  className,
  ...props
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-3 px-6 py-12 text-center",
        className
      )}
      {...props}
    >
      {icon ? (
        <div className="flex h-10 w-10 items-center justify-center rounded-md border border-border bg-surface-2 text-foreground-muted [&_svg]:size-5">
          {icon}
        </div>
      ) : null}
      <div className="space-y-1">
        <p className="text-sm font-semibold text-foreground">{title}</p>
        {description ? (
          <p className="text-xs text-foreground-muted max-w-sm">{description}</p>
        ) : null}
      </div>
      {action}
    </div>
  );
}
