"use client";

import { useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";
import { getVaultStatus } from "@/lib/api";
import type { VaultStatus } from "@/types/api";
import { PageHeader, PageBody } from "@/components/shell/page-header";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { VaultStatusCard } from "@/features/vault/_components/vault-status-card";

export default function VaultStatusPage() {
  const [status, setStatus] = useState<VaultStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      const res = await getVaultStatus();
      if (res.ok) setStatus(res.data);
      else setError(res.error.message);
    } catch {
      setError("Network error — is the backend running?");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  return (
    <>
      <PageHeader
        breadcrumb={["Vault", "Status"]}
        title="Vault Status"
        description="Seal state, initialization, and unseal mode."
        actions={
          <Button variant="outline" size="sm" onClick={refresh} disabled={loading}>
            <RefreshCw className={loading ? "animate-spin" : undefined} /> Refresh
          </Button>
        }
      />
      <PageBody className="space-y-4">
        {loading && !status && (
          <Card className="p-6">
            <Skeleton className="h-4 w-24" />
            <Skeleton className="mt-2 h-8 w-full" />
            <Skeleton className="mt-2 h-4 w-1/2" />
          </Card>
        )}

        {error && (
          <Card className="border-[color:var(--danger)]/30 bg-[color:var(--danger-bg)] p-4 text-xs text-[color:var(--danger)]">
            {error}
          </Card>
        )}

        {status && <VaultStatusCard status={status} />}
      </PageBody>
    </>
  );
}
