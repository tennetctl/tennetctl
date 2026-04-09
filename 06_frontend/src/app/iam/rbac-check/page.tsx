"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ShieldCheck, Search } from "lucide-react";
import { checkRbac, getEffectivePermissions, listPermissions } from "@/lib/api";
import { useAuth } from "@/components/providers/auth-provider";
import { PageHeader, PageBody } from "@/components/shell/page-header";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import type { PermissionData, RbacCheckResult, EffectivePermissionsData } from "@/types/api";

export default function RbacCheckPage() {
  const auth = useAuth();
  const router = useRouter();

  const isAuthenticated = auth.status === "authenticated";
  const token = isAuthenticated ? auth.accessToken : "";

  // Form state
  const [userId, setUserId] = useState("");
  const [resource, setResource] = useState("");
  const [action, setAction] = useState("");
  const [orgId, setOrgId] = useState("");
  const [workspaceId, setWorkspaceId] = useState("");

  // Permissions list (for dropdowns)
  const [permissions, setPermissions] = useState<PermissionData[]>([]);
  const [permsLoading, setPermsLoading] = useState(false);

  // Check result
  const [checking, setChecking] = useState(false);
  const [checkResult, setCheckResult] = useState<RbacCheckResult | null>(null);
  const [checkError, setCheckError] = useState<string | null>(null);

  // Effective permissions
  const [effectiveUserId, setEffectiveUserId] = useState("");
  const [effective, setEffective] = useState<EffectivePermissionsData | null>(null);
  const [effectiveLoading, setEffectiveLoading] = useState(false);
  const [effectiveError, setEffectiveError] = useState<string | null>(null);

  useEffect(() => {
    if (auth.status !== "authenticated") return;
    setPermsLoading(true);
    listPermissions(token)
      .then((res) => {
        if (res.ok) setPermissions(res.data.items);
      })
      .catch(() => {})
      .finally(() => setPermsLoading(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [auth.status]);

  // Available actions for selected resource
  const resourceOptions = [...new Set(permissions.map((p) => p.resource))].sort();
  const actionOptions = permissions
    .filter((p) => p.resource === resource)
    .map((p) => p.action)
    .sort();

  async function handleCheck(e: React.FormEvent) {
    e.preventDefault();
    setCheckError(null);
    setCheckResult(null);
    setChecking(true);
    try {
      const res = await checkRbac(
        {
          user_id: userId,
          resource,
          action,
          org_id: orgId || undefined,
          workspace_id: workspaceId || undefined,
        },
        token
      );
      if (!res.ok) {
        setCheckError(res.error.message);
        return;
      }
      setCheckResult(res.data);
    } catch {
      setCheckError("Network error.");
    } finally {
      setChecking(false);
    }
  }

  async function handleEffective(e: React.FormEvent) {
    e.preventDefault();
    if (!effectiveUserId.trim()) return;
    setEffectiveError(null);
    setEffective(null);
    setEffectiveLoading(true);
    try {
      const res = await getEffectivePermissions(effectiveUserId.trim(), token);
      if (!res.ok) {
        setEffectiveError(res.error.message);
        return;
      }
      setEffective(res.data);
    } catch {
      setEffectiveError("Network error.");
    } finally {
      setEffectiveLoading(false);
    }
  }

  if (auth.status === "loading") {
    return (
      <>
        <PageHeader breadcrumb={["IAM", "RBAC Check"]} title="RBAC Check" description="Test permission checks and inspect effective permissions." />
        <PageBody>
          <Card>
            <div className="space-y-2 p-4">
              {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-8 w-full" />)}
            </div>
          </Card>
        </PageBody>
      </>
    );
  }

  if (auth.status === "unauthenticated") {
    return (
      <>
        <PageHeader breadcrumb={["IAM", "RBAC Check"]} title="RBAC Check" description="Test permission checks and inspect effective permissions." />
        <PageBody>
          <Card>
            <EmptyState
              icon={<ShieldCheck />}
              title="Sign in required"
              description="Sign in to use the RBAC checker."
              action={<Button size="sm" onClick={() => router.push("/iam")}>Go to sign in</Button>}
            />
          </Card>
        </PageBody>
      </>
    );
  }

  return (
    <>
      <PageHeader
        breadcrumb={["IAM", "RBAC Check"]}
        title="RBAC Check"
        description="Test permission decisions and inspect a user's effective permissions."
      />

      <PageBody className="grid gap-6 lg:grid-cols-2">
        {/* Check panel */}
        <Card>
          <CardHeader>
            <CardTitle>Permission Check</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleCheck} className="space-y-4">
              <div className="space-y-1.5">
                <Label htmlFor="check-user-id">User ID</Label>
                <Input
                  id="check-user-id"
                  value={userId}
                  placeholder="usr_xxxxxxxxxxxxxxxx"
                  onChange={(e) => setUserId(e.target.value)}
                  className="font-mono text-xs"
                  required
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="check-resource">Resource</Label>
                {permsLoading ? (
                  <Skeleton className="h-8 w-full" />
                ) : (
                  <select
                    id="check-resource"
                    value={resource}
                    onChange={(e) => { setResource(e.target.value); setAction(""); }}
                    className="w-full rounded-md border border-border bg-surface-2 px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
                    required
                  >
                    <option value="">Select resource…</option>
                    {resourceOptions.map((r) => (
                      <option key={r} value={r}>{r}</option>
                    ))}
                    {resourceOptions.length === 0 && (
                      <option disabled>No permissions loaded</option>
                    )}
                  </select>
                )}
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="check-action">Action</Label>
                <select
                  id="check-action"
                  value={action}
                  onChange={(e) => setAction(e.target.value)}
                  className="w-full rounded-md border border-border bg-surface-2 px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
                  required
                  disabled={!resource}
                >
                  <option value="">Select action…</option>
                  {actionOptions.map((a) => (
                    <option key={a} value={a}>{a}</option>
                  ))}
                </select>
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="check-org-id">
                  Org ID <span className="text-foreground-subtle">(optional)</span>
                </Label>
                <Input
                  id="check-org-id"
                  value={orgId}
                  placeholder="org_xxxxxxxxxxxxxxxx"
                  onChange={(e) => setOrgId(e.target.value)}
                  className="font-mono text-xs"
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="check-ws-id">
                  Workspace ID <span className="text-foreground-subtle">(optional)</span>
                </Label>
                <Input
                  id="check-ws-id"
                  value={workspaceId}
                  placeholder="ws_xxxxxxxxxxxxxxxx"
                  onChange={(e) => setWorkspaceId(e.target.value)}
                  className="font-mono text-xs"
                />
              </div>

              {checkError && (
                <p className="rounded-md border border-[color:var(--danger)]/30 bg-[color:var(--danger-bg)] px-3 py-2 text-xs text-[color:var(--danger)]">
                  {checkError}
                </p>
              )}

              <Button type="submit" size="sm" disabled={checking || !userId || !resource || !action}>
                <Search className="size-3.5" />
                {checking ? "Checking…" : "Check Permission"}
              </Button>
            </form>

            {checkResult && (
              <div className={`mt-4 rounded-md border px-4 py-3 ${
                checkResult.allowed
                  ? "border-[color:var(--success)]/30 bg-[color:var(--success-bg)]"
                  : "border-[color:var(--danger)]/30 bg-[color:var(--danger-bg)]"
              }`}>
                <div className="flex items-center gap-2">
                  <span className="text-lg">{checkResult.allowed ? "✅" : "❌"}</span>
                  <span className={`text-sm font-semibold ${
                    checkResult.allowed ? "text-[color:var(--success)]" : "text-[color:var(--danger)]"
                  }`}>
                    {checkResult.allowed ? "Allowed" : "Denied"}
                  </span>
                </div>
                <p className="mt-1.5 font-mono text-xs text-foreground-muted">
                  {checkResult.resource}:{checkResult.action}
                </p>
                {checkResult.reason && (
                  <p className="mt-1 text-xs text-foreground-muted">{checkResult.reason}</p>
                )}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Effective permissions panel */}
        <Card>
          <CardHeader>
            <CardTitle>Effective Permissions</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleEffective} className="flex gap-2">
              <Input
                value={effectiveUserId}
                placeholder="User ID…"
                onChange={(e) => setEffectiveUserId(e.target.value)}
                className="font-mono text-xs"
                required
              />
              <Button type="submit" size="sm" disabled={effectiveLoading || !effectiveUserId.trim()}>
                {effectiveLoading ? "Loading…" : "Fetch"}
              </Button>
            </form>

            {effectiveError && (
              <p className="mt-3 text-xs text-[color:var(--danger)]">{effectiveError}</p>
            )}

            {effectiveLoading && (
              <div className="mt-4 space-y-2">
                {[...Array(4)].map((_, i) => (
                  <Skeleton key={i} className="h-6 w-full" />
                ))}
              </div>
            )}

            {!effectiveLoading && effective && (
              <div className="mt-4">
                <p className="mb-3 text-xs text-foreground-muted">
                  {effective.permissions.length} permission{effective.permissions.length !== 1 ? "s" : ""} for{" "}
                  <span className="font-mono">{effective.user_id}</span>
                </p>
                {effective.permissions.length === 0 ? (
                  <p className="text-xs text-foreground-muted">No permissions assigned.</p>
                ) : (
                  <div className="flex flex-wrap gap-1.5">
                    {effective.permissions.map((perm, i) => (
                      <Badge key={`${perm.resource}:${perm.action}:${perm.tier}:${i}`} variant="outline" className="font-mono text-[10px]">
                        {perm.resource}:{perm.action}<span className="ml-1 text-[9px] opacity-60">({perm.tier})</span>
                      </Badge>
                    ))}
                  </div>
                )}
              </div>
            )}

            {!effectiveLoading && !effective && !effectiveError && (
              <div className="mt-6">
                <EmptyState
                  icon={<ShieldCheck />}
                  title="No user selected"
                  description="Enter a user ID above to see their effective permissions."
                />
              </div>
            )}
          </CardContent>
        </Card>
      </PageBody>
    </>
  );
}
