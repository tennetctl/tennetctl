import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/cn";

const badgeVariants = cva(
  "inline-flex items-center gap-1 rounded-sm border px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider",
  {
    variants: {
      variant: {
        default:
          "border-border bg-surface-2 text-foreground-muted",
        outline:
          "border-border text-foreground-muted",
        success:
          "border-[color:var(--success)]/30 bg-[color:var(--success-bg)] text-[color:var(--success)]",
        warning:
          "border-[color:var(--warning)]/30 bg-[color:var(--warning-bg)] text-[color:var(--warning)]",
        danger:
          "border-[color:var(--danger)]/30 bg-[color:var(--danger-bg)] text-[color:var(--danger)]",
        info:
          "border-[color:var(--info)]/30 bg-[color:var(--info-bg)] text-[color:var(--info)]",
      },
    },
    defaultVariants: { variant: "default" },
  }
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />;
}

export { badgeVariants };
