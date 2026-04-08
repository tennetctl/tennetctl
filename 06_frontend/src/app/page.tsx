import Link from "next/link";
import { ArrowRight, Activity } from "lucide-react";
import { PageHeader, PageBody } from "@/components/shell/page-header";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { NAV_MODULES } from "@/components/shell/nav-config";

const STATS = [
  { label: "Active sessions", value: "—", hint: "across all orgs" },
  { label: "Users", value: "—", hint: "total registered" },
  { label: "Audit events (24h)", value: "—", hint: "success + failure" },
  { label: "Vault status", value: "—", hint: "seal state" },
];

export default function HomePage() {
  return (
    <>
      <PageHeader
        breadcrumb={["tennetctl", "Overview"]}
        title="Operator Console"
        description="Super-admin view across IAM, Vault, and Audit."
        actions={
          <Badge variant="success">
            <Activity className="h-3 w-3" /> Operational
          </Badge>
        }
      />
      <PageBody className="space-y-5 sm:space-y-6">
        {/* Stats — 2 cols on mobile, 4 on desktop */}
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          {STATS.map((s) => (
            <Card key={s.label} className="p-3 sm:p-4">
              <p className="text-[10px] font-semibold uppercase tracking-wider text-foreground-subtle">
                {s.label}
              </p>
              <p className="mt-1.5 font-mono text-xl font-semibold tabular-nums text-foreground sm:text-2xl">
                {s.value}
              </p>
              <p className="mt-0.5 text-[11px] text-foreground-muted">{s.hint}</p>
            </Card>
          ))}
        </div>

        {/* Modules — 1 col on mobile, 3 on desktop */}
        <section>
          <h2 className="mb-3 text-[10px] font-semibold uppercase tracking-wider text-foreground-subtle">
            Modules
          </h2>
          <div className="grid gap-3 sm:grid-cols-2 md:grid-cols-3">
            {NAV_MODULES.map((m) => {
              const Icon = m.icon;
              return (
                <Link key={m.key} href={m.href}>
                  <Card className="group h-full p-4 transition-colors hover:bg-surface-2 sm:p-5">
                    <div className="flex items-start justify-between">
                      <div className="flex h-8 w-8 items-center justify-center rounded-md border border-border bg-surface-2 sm:h-9 sm:w-9">
                        <Icon className="h-4 w-4 text-foreground" />
                      </div>
                      <span className="font-mono text-[10px] text-foreground-subtle">
                        {m.number}
                      </span>
                    </div>
                    <div className="mt-3 flex items-center gap-2 sm:mt-4">
                      <h3 className="text-sm font-semibold text-foreground">
                        {m.label}
                      </h3>
                      <ArrowRight className="h-3 w-3 text-foreground-subtle transition-transform group-hover:translate-x-0.5" />
                    </div>
                    <p className="mt-1 text-xs text-foreground-muted">
                      {m.description}
                    </p>
                    <div className="mt-3 flex flex-wrap gap-1 sm:mt-4">
                      {m.groups.flatMap((g) => g.items).slice(0, 4).map((it) => (
                        <Badge key={it.href} variant="outline">
                          {it.label}
                        </Badge>
                      ))}
                    </div>
                  </Card>
                </Link>
              );
            })}
          </div>
        </section>
      </PageBody>
    </>
  );
}
