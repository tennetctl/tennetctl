"use client";

import { Lock, Unlock, KeyRound, Clock } from "lucide-react";
import type { VaultStatus } from "@/types/api";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export function VaultStatusCard({ status }: { status: VaultStatus }) {
  const sealed = status.status === "sealed";
  const Icon = sealed ? Lock : Unlock;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Icon className="h-4 w-4" /> Vault
        </CardTitle>
        <Badge variant={sealed ? "danger" : "success"}>{status.status}</Badge>
      </CardHeader>
      <CardContent className="grid gap-4 sm:grid-cols-3">
        <Metric
          icon={<KeyRound className="h-3.5 w-3.5" />}
          label="Initialized"
          value={status.initialized ? "Yes" : "No"}
        />
        <Metric
          icon={<Lock className="h-3.5 w-3.5" />}
          label="Unseal mode"
          value={status.unseal_mode}
        />
        <Metric
          icon={<Clock className="h-3.5 w-3.5" />}
          label="Initialized at"
          value={
            status.initialized_at
              ? new Date(status.initialized_at).toLocaleString()
              : "—"
          }
        />
      </CardContent>
    </Card>
  );
}

function Metric({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
}) {
  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider text-foreground-subtle">
        {icon} {label}
      </div>
      <p className="truncate font-mono text-sm text-foreground">{value}</p>
    </div>
  );
}
