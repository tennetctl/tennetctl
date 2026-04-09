"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { FolderKey, Plus, Trash2, Shield } from "lucide-react";
import {
  listPlatformRoles,
  createPlatformRole,
  deletePlatformRole,
  listPlatformRolePermissions,
  addPlatformRolePermission,
  removePlatformRolePermission,
  listPermissions,
  listOrgRoles,
  createOrgRole,
  deleteOrgRole,
  listWorkspaceRoles,
  createWorkspaceRole,
  deleteWorkspaceRole,
  listOrgs,
  listWorkspaces,
} from "@/lib/api";
import { useAuth } from "@/components/providers/auth-provider";
import { PageHeader, PageBody } from "@/components/shell/page-header";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from "@/components/ui/table";
import type {
  PlatformRoleData,
  OrgRoleData,
  WorkspaceRoleData,
  PermissionData,
  RolePermissionData,
} from "@/types/api";
import type { OrgSummary, WorkspaceSummary } from "@/lib/api";

type Tab = "platform" | "org" | "workspace";

// ---------------------------------------------------------------------------
// Create Role Modal (shared)
// ---------------------------------------------------------------------------

interface CreateRoleModalProps {
  title: string;
  onSubmit: (body: {
    name: string;
    code: string;
    category_code: string;
  }) => Promise<void>;
  onClose: () => void;
  error: string | null;
  submitting: boolean;
}

function CreateRoleModal({
  title,
  onSubmit,
  onClose,
  error,
  submitting,
}: CreateRoleModalProps) {
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [categoryCode, setCategoryCode] = useState("custom");
  const backdropRef = { current: null as HTMLDivElement | null };

  function deriveCode(v: string) {
    return v.toLowerCase().replace(/\s+/g, "_").replace(/[^a-z0-9_]/g, "");
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    await onSubmit({ name, code, category_code: categoryCode });
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      onClick={(e) => {
        if (e.target === (backdropRef.current as unknown)) onClose();
      }}
      ref={(el) => {
        backdropRef.current = el;
      }}
    >
      <div className="relative w-full max-w-md rounded-md border border-border bg-surface shadow-xl">
        <div className="flex items-center justify-between border-b border-border px-5 py-4">
          <h2 className="text-sm font-semibold">{title}</h2>
          <button
            onClick={onClose}
            className="rounded-sm p-1 text-foreground-muted hover:bg-surface-3 hover:text-foreground"
          >
            ×
          </button>
        </div>
        <form onSubmit={handleSubmit} className="space-y-4 p-5">
          <div className="space-y-1.5">
            <Label htmlFor="role-name">Name</Label>
            <Input
              id="role-name"
              value={name}
              placeholder="Admin"
              onChange={(e) => {
                setName(e.target.value);
                if (!code) setCode(deriveCode(e.target.value));
              }}
              required
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="role-code">Code</Label>
            <Input
              id="role-code"
              value={code}
              placeholder="admin"
              className="font-mono"
              onChange={(e) => setCode(deriveCode(e.target.value))}
              required
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="role-category">Category</Label>
            <select
              id="role-category"
              value={categoryCode}
              onChange={(e) => setCategoryCode(e.target.value)}
              className="w-full rounded-md border border-border bg-surface-2 px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
            >
              <option value="custom">custom</option>
              <option value="system">system</option>
              <option value="ops">ops</option>
              <option value="support">support</option>
              <option value="developer">developer</option>
              <option value="finance">finance</option>
            </select>
          </div>
          {error && (
            <p className="rounded-md border border-[color:var(--danger)]/30 bg-[color:var(--danger-bg)] px-3 py-2 text-xs text-[color:var(--danger)]">
              {error}
            </p>
          )}
          <div className="flex justify-end gap-2 pt-1">
            <Button type="button" variant="outline" size="sm" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" size="sm" disabled={submitting}>
              {submitting ? "Creating…" : "Create Role"}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Permissions Side Panel
// ---------------------------------------------------------------------------

interface PermissionsPanelProps {
  roleId: string;
  roleName: string;
  accessToken: string;
  onClose: () => void;
}

function PermissionsPanel({
  roleId,
  roleName,
  accessToken,
  onClose,
}: PermissionsPanelProps) {
  const [allPerms, setAllPerms] = useState<PermissionData[]>([]);
  const [rolePerms, setRolePerms] = useState<RolePermissionData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [toggling, setToggling] = useState<string | null>(null);
  const backdropRef = { current: null as HTMLDivElement | null };

  useEffect(() => {
    setLoading(true);
    Promise.all([
      listPermissions(accessToken),
      listPlatformRolePermissions(roleId, accessToken),
    ])
      .then(([allRes, roleRes]) => {
        if (allRes.ok) setAllPerms(allRes.data.items);
        else setError(allRes.error.message);
        if (roleRes.ok) setRolePerms(roleRes.data.items);
      })
      .catch(() => setError("Network error."))
      .finally(() => setLoading(false));
  }, [roleId, accessToken]);

  const assignedIds = new Set(rolePerms.map((rp) => rp.permission_id));

  async function toggle(perm: PermissionData) {
    setToggling(perm.id);
    try {
      if (assignedIds.has(perm.id)) {
        await removePlatformRolePermission(roleId, perm.id, accessToken);
        setRolePerms((prev) => prev.filter((rp) => rp.permission_id !== perm.id));
      } else {
        const res = await addPlatformRolePermission(roleId, perm.id, accessToken);
        if (res.ok) {
          setRolePerms((prev) => [
            ...prev,
            {
              id: res.data.id,
              role_id: roleId,
              permission_id: perm.id,
              resource: perm.resource,
              action: perm.action,
            },
          ]);
        }
      }
    } finally {
      setToggling(null);
    }
  }

  // Group by resource
  const grouped: Record<string, PermissionData[]> = {};
  for (const p of allPerms) {
    if (!grouped[p.resource]) grouped[p.resource] = [];
    grouped[p.resource].push(p);
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      onClick={(e) => {
        if (e.target === (backdropRef.current as unknown)) onClose();
      }}
      ref={(el) => {
        backdropRef.current = el;
      }}
    >
      <div className="relative flex h-[85vh] w-full max-w-2xl flex-col rounded-md border border-border bg-surface shadow-xl">
        <div className="flex shrink-0 items-center justify-between border-b border-border px-5 py-4">
          <div className="space-y-0.5">
            <h2 className="text-sm font-semibold">{roleName}</h2>
            <p className="text-xs text-foreground-muted">
              Permissions — {rolePerms.length} assigned
            </p>
          </div>
          <button
            onClick={onClose}
            className="rounded-sm p-1 text-foreground-muted hover:bg-surface-3 hover:text-foreground"
          >
            ×
          </button>
        </div>

        <div className="min-h-0 flex-1 overflow-auto p-5">
          {loading && (
            <div className="space-y-2">
              {[...Array(6)].map((_, i) => (
                <Skeleton key={i} className="h-8 w-full" />
              ))}
            </div>
          )}
          {!loading && error && (
            <p className="text-xs text-[color:var(--danger)]">{error}</p>
          )}
          {!loading && !error && allPerms.length === 0 && (
            <p className="text-xs text-foreground-muted">No permissions registered yet.</p>
          )}
          {!loading &&
            !error &&
            Object.entries(grouped).map(([resource, perms]) => (
              <div key={resource} className="mb-5">
                <p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-foreground-muted">
                  {resource}
                </p>
                <div className="flex flex-wrap gap-2">
                  {perms.map((p) => {
                    const assigned = assignedIds.has(p.id);
                    return (
                      <button
                        key={p.id}
                        disabled={toggling === p.id}
                        onClick={() => toggle(p)}
                        className={`rounded-sm border px-2 py-1 text-[11px] font-mono transition-colors ${
                          assigned
                            ? "border-[color:var(--success)]/40 bg-[color:var(--success-bg)] text-[color:var(--success)]"
                            : "border-border bg-surface-2 text-foreground-muted hover:border-border hover:bg-surface-3"
                        } ${toggling === p.id ? "opacity-50" : ""}`}
                      >
                        {p.action}
                      </button>
                    );
                  })}
                </div>
              </div>
            ))}
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Role Table (shared)
// ---------------------------------------------------------------------------

type AnyRole = PlatformRoleData | OrgRoleData | WorkspaceRoleData;

interface RoleTableProps {
  roles: AnyRole[];
  loading: boolean;
  error: string | null;
  isAuthenticated: boolean;
  onManagePerms: (role: AnyRole) => void;
  onDelete: (role: AnyRole) => void;
  deletingId: string | null;
  onNew: () => void;
}

function RoleTable({
  roles,
  loading,
  error,
  isAuthenticated,
  onManagePerms,
  onDelete,
  deletingId,
  onNew,
}: RoleTableProps) {
  if (loading) {
    return (
      <div className="space-y-2 p-4">
        {[...Array(4)].map((_, i) => (
          <Skeleton key={i} className="h-8 w-full" />
        ))}
      </div>
    );
  }
  if (error) {
    return (
      <EmptyState
        icon={<FolderKey />}
        title="Could not load roles"
        description={error}
      />
    );
  }
  if (roles.length === 0) {
    return (
      <EmptyState
        icon={<FolderKey />}
        title="No roles yet"
        description="Create the first role."
        action={
          isAuthenticated ? (
            <Button size="sm" onClick={onNew}>
              <Plus className="size-3.5" />
              New Role
            </Button>
          ) : undefined
        }
      />
    );
  }
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Name</TableHead>
          <TableHead>Code</TableHead>
          <TableHead>Category</TableHead>
          <TableHead>Type</TableHead>
          <TableHead>Status</TableHead>
          <TableHead className="w-24" />
        </TableRow>
      </TableHeader>
      <TableBody>
        {roles.map((r) => (
          <TableRow key={r.id}>
            <TableCell className="font-medium">{r.name}</TableCell>
            <TableCell className="font-mono text-[11px] text-foreground-muted">
              {r.code}
            </TableCell>
            <TableCell className="text-xs text-foreground-muted">{r.category_label ?? r.category_code ?? "—"}</TableCell>
            <TableCell>
              {r.is_system ? (
                <Badge variant="info">system</Badge>
              ) : (
                <Badge variant="outline">custom</Badge>
              )}
            </TableCell>
            <TableCell>
              {r.is_active ? (
                <Badge variant="success">active</Badge>
              ) : (
                <Badge variant="default">inactive</Badge>
              )}
            </TableCell>
            <TableCell>
              <div className="flex items-center gap-1">
                <Button
                  variant="ghost"
                  size="icon"
                  title="Manage permissions"
                  onClick={() => onManagePerms(r)}
                  disabled={!isAuthenticated}
                >
                  <Shield className="size-3.5 text-foreground-muted" />
                </Button>
                {!r.is_system && (
                  <Button
                    variant="ghost"
                    size="icon"
                    title="Delete role"
                    disabled={deletingId === r.id || !isAuthenticated}
                    onClick={() => onDelete(r)}
                  >
                    <Trash2 className="size-3.5 text-foreground-muted" />
                  </Button>
                )}
              </div>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function IamRolesPage() {
  const auth = useAuth();
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<Tab>("platform");

  // Platform
  const [platformRoles, setPlatformRoles] = useState<PlatformRoleData[]>([]);
  const [platformLoading, setPlatformLoading] = useState(true);
  const [platformError, setPlatformError] = useState<string | null>(null);
  const [platformDeletingId, setPlatformDeletingId] = useState<string | null>(null);
  const [showPlatformCreate, setShowPlatformCreate] = useState(false);
  const [platformCreateError, setPlatformCreateError] = useState<string | null>(null);
  const [platformCreateSubmitting, setPlatformCreateSubmitting] = useState(false);

  // Org
  const [orgs, setOrgs] = useState<OrgSummary[]>([]);
  const [selectedOrgId, setSelectedOrgId] = useState("");
  const [orgRoles, setOrgRoles] = useState<OrgRoleData[]>([]);
  const [orgLoading, setOrgLoading] = useState(false);
  const [orgError, setOrgError] = useState<string | null>(null);
  const [orgDeletingId, setOrgDeletingId] = useState<string | null>(null);
  const [showOrgCreate, setShowOrgCreate] = useState(false);
  const [orgCreateError, setOrgCreateError] = useState<string | null>(null);
  const [orgCreateSubmitting, setOrgCreateSubmitting] = useState(false);

  // Workspace
  const [workspaces, setWorkspaces] = useState<WorkspaceSummary[]>([]);
  const [selectedWsId, setSelectedWsId] = useState("");
  const [wsRoles, setWsRoles] = useState<WorkspaceRoleData[]>([]);
  const [wsLoading, setWsLoading] = useState(false);
  const [wsError, setWsError] = useState<string | null>(null);
  const [wsDeletingId, setWsDeletingId] = useState<string | null>(null);
  const [showWsCreate, setShowWsCreate] = useState(false);
  const [wsCreateError, setWsCreateError] = useState<string | null>(null);
  const [wsCreateSubmitting, setWsCreateSubmitting] = useState(false);

  // Permissions panel
  const [permsPanelRole, setPermsPanelRole] = useState<AnyRole | null>(null);

  const isAuthenticated = auth.status === "authenticated";
  const token = isAuthenticated ? auth.accessToken : "";

  // Load platform roles
  useEffect(() => {
    if (auth.status !== "authenticated") return;
    setPlatformLoading(true);
    listPlatformRoles(token)
      .then((res) => {
        if (res.ok) setPlatformRoles(res.data.items);
        else setPlatformError(res.error.message);
      })
      .catch(() => setPlatformError("Network error."))
      .finally(() => setPlatformLoading(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [auth.status]);

  // Load orgs for selector
  useEffect(() => {
    if (auth.status !== "authenticated") return;
    listOrgs(token)
      .then((res) => {
        if (res.ok) {
          setOrgs(res.data.items);
          if (res.data.items.length > 0) setSelectedOrgId(res.data.items[0].id);
        }
      })
      .catch(() => {});
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [auth.status]);

  // Load workspaces for selector
  useEffect(() => {
    if (auth.status !== "authenticated") return;
    listWorkspaces(token)
      .then((res) => {
        if (res.ok) {
          setWorkspaces(res.data.items);
          if (res.data.items.length > 0) setSelectedWsId(res.data.items[0].id);
        }
      })
      .catch(() => {});
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [auth.status]);

  // Load org roles when org selected
  const fetchOrgRoles = useCallback(
    (orgId: string) => {
      if (!orgId || !token) return;
      setOrgLoading(true);
      setOrgError(null);
      listOrgRoles(orgId, token)
        .then((res) => {
          if (res.ok) setOrgRoles(res.data.items);
          else setOrgError(res.error.message);
        })
        .catch(() => setOrgError("Network error."))
        .finally(() => setOrgLoading(false));
    },
    [token]
  );

  useEffect(() => {
    if (activeTab === "org" && selectedOrgId) fetchOrgRoles(selectedOrgId);
  }, [activeTab, selectedOrgId, fetchOrgRoles]);

  // Load workspace roles when ws selected
  const fetchWsRoles = useCallback(
    (wsId: string) => {
      if (!wsId || !token) return;
      setWsLoading(true);
      setWsError(null);
      listWorkspaceRoles(wsId, token)
        .then((res) => {
          if (res.ok) setWsRoles(res.data.items);
          else setWsError(res.error.message);
        })
        .catch(() => setWsError("Network error."))
        .finally(() => setWsLoading(false));
    },
    [token]
  );

  useEffect(() => {
    if (activeTab === "workspace" && selectedWsId) fetchWsRoles(selectedWsId);
  }, [activeTab, selectedWsId, fetchWsRoles]);

  // Unauthenticated guard
  if (auth.status === "loading") {
    return (
      <>
        <PageHeader breadcrumb={["IAM", "Roles"]} title="Roles" description="Platform, org, and workspace-scoped roles." />
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
        <PageHeader breadcrumb={["IAM", "Roles"]} title="Roles" description="Platform, org, and workspace-scoped roles." />
        <PageBody>
          <Card>
            <EmptyState
              icon={<FolderKey />}
              title="Sign in required"
              description="Sign in to view roles."
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
        breadcrumb={["IAM", "Roles"]}
        title="Roles"
        description="Platform, org, and workspace-scoped roles with permission assignments."
        actions={
          <Button
            size="sm"
            onClick={() => {
              if (activeTab === "platform") setShowPlatformCreate(true);
              else if (activeTab === "org") setShowOrgCreate(true);
              else setShowWsCreate(true);
            }}
          >
            <Plus className="size-3.5" />
            New Role
          </Button>
        }
      />

      <PageBody>
        {/* Tab bar */}
        <div className="mb-4 flex gap-1 rounded-md border border-border bg-surface-2 p-1 w-fit">
          {(["platform", "org", "workspace"] as Tab[]).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`rounded px-4 py-1.5 text-xs font-medium capitalize transition-colors ${
                activeTab === tab
                  ? "bg-surface text-foreground shadow-sm"
                  : "text-foreground-muted hover:text-foreground"
              }`}
            >
              {tab === "platform" ? "Platform Roles" : tab === "org" ? "Org Roles" : "Workspace Roles"}
            </button>
          ))}
        </div>

        {/* Platform tab */}
        {activeTab === "platform" && (
          <Card>
            <CardHeader>
              <CardTitle>Platform Roles</CardTitle>
            </CardHeader>
            <RoleTable
              roles={platformRoles}
              loading={platformLoading}
              error={platformError}
              isAuthenticated={isAuthenticated}
              deletingId={platformDeletingId}
              onNew={() => setShowPlatformCreate(true)}
              onManagePerms={(r) => setPermsPanelRole(r)}
              onDelete={async (r) => {
                if (!confirm(`Delete role "${r.name}"?`)) return;
                setPlatformDeletingId(r.id);
                try {
                  await deletePlatformRole(r.id, token);
                  setPlatformRoles((prev) => prev.filter((pr) => pr.id !== r.id));
                } finally {
                  setPlatformDeletingId(null);
                }
              }}
            />
          </Card>
        )}

        {/* Org tab */}
        {activeTab === "org" && (
          <Card>
            <CardHeader>
              <div className="flex items-center gap-3">
                <CardTitle>Org Roles</CardTitle>
                <select
                  value={selectedOrgId}
                  onChange={(e) => setSelectedOrgId(e.target.value)}
                  className="rounded-md border border-border bg-surface-2 px-2 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-ring"
                >
                  {orgs.length === 0 && (
                    <option value="">No orgs available</option>
                  )}
                  {orgs.map((o) => (
                    <option key={o.id} value={o.id}>
                      {o.name ?? o.slug ?? o.id}
                    </option>
                  ))}
                </select>
              </div>
            </CardHeader>
            <RoleTable
              roles={orgRoles}
              loading={orgLoading}
              error={orgError}
              isAuthenticated={isAuthenticated}
              deletingId={orgDeletingId}
              onNew={() => setShowOrgCreate(true)}
              onManagePerms={(r) => setPermsPanelRole(r)}
              onDelete={async (r) => {
                if (!confirm(`Delete role "${r.name}"?`)) return;
                setOrgDeletingId(r.id);
                try {
                  await deleteOrgRole(selectedOrgId, r.id, token);
                  setOrgRoles((prev) => prev.filter((pr) => pr.id !== r.id));
                } finally {
                  setOrgDeletingId(null);
                }
              }}
            />
          </Card>
        )}

        {/* Workspace tab */}
        {activeTab === "workspace" && (
          <Card>
            <CardHeader>
              <div className="flex items-center gap-3">
                <CardTitle>Workspace Roles</CardTitle>
                <select
                  value={selectedWsId}
                  onChange={(e) => setSelectedWsId(e.target.value)}
                  className="rounded-md border border-border bg-surface-2 px-2 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-ring"
                >
                  {workspaces.length === 0 && (
                    <option value="">No workspaces available</option>
                  )}
                  {workspaces.map((w) => (
                    <option key={w.id} value={w.id}>
                      {w.name ?? w.slug ?? w.id}
                    </option>
                  ))}
                </select>
              </div>
            </CardHeader>
            <RoleTable
              roles={wsRoles}
              loading={wsLoading}
              error={wsError}
              isAuthenticated={isAuthenticated}
              deletingId={wsDeletingId}
              onNew={() => setShowWsCreate(true)}
              onManagePerms={(r) => setPermsPanelRole(r)}
              onDelete={async (r) => {
                if (!confirm(`Delete role "${r.name}"?`)) return;
                setWsDeletingId(r.id);
                try {
                  await deleteWorkspaceRole(selectedWsId, r.id, token);
                  setWsRoles((prev) => prev.filter((pr) => pr.id !== r.id));
                } finally {
                  setWsDeletingId(null);
                }
              }}
            />
          </Card>
        )}
      </PageBody>

      {/* Platform create modal */}
      {showPlatformCreate && (
        <CreateRoleModal
          title="Create Platform Role"
          error={platformCreateError}
          submitting={platformCreateSubmitting}
          onClose={() => {
            setShowPlatformCreate(false);
            setPlatformCreateError(null);
          }}
          onSubmit={async (body) => {
            setPlatformCreateError(null);
            setPlatformCreateSubmitting(true);
            try {
              const res = await createPlatformRole(body, token);
              if (!res.ok) {
                setPlatformCreateError(res.error.message);
                return;
              }
              setPlatformRoles((prev) => [res.data, ...prev]);
              setShowPlatformCreate(false);
            } catch {
              setPlatformCreateError("Network error.");
            } finally {
              setPlatformCreateSubmitting(false);
            }
          }}
        />
      )}

      {/* Org create modal */}
      {showOrgCreate && selectedOrgId && (
        <CreateRoleModal
          title="Create Org Role"
          error={orgCreateError}
          submitting={orgCreateSubmitting}
          onClose={() => {
            setShowOrgCreate(false);
            setOrgCreateError(null);
          }}
          onSubmit={async (body) => {
            setOrgCreateError(null);
            setOrgCreateSubmitting(true);
            try {
              const res = await createOrgRole(selectedOrgId, body, token);
              if (!res.ok) {
                setOrgCreateError(res.error.message);
                return;
              }
              setOrgRoles((prev) => [res.data, ...prev]);
              setShowOrgCreate(false);
            } catch {
              setOrgCreateError("Network error.");
            } finally {
              setOrgCreateSubmitting(false);
            }
          }}
        />
      )}

      {/* Workspace create modal */}
      {showWsCreate && selectedWsId && (
        <CreateRoleModal
          title="Create Workspace Role"
          error={wsCreateError}
          submitting={wsCreateSubmitting}
          onClose={() => {
            setShowWsCreate(false);
            setWsCreateError(null);
          }}
          onSubmit={async (body) => {
            setWsCreateError(null);
            setWsCreateSubmitting(true);
            try {
              const ws = workspaces.find((w) => w.id === selectedWsId);
              if (!ws) {
                setWsCreateError("No workspace selected.");
                return;
              }
              const res = await createWorkspaceRole(selectedWsId, { ...body, org_id: ws.org_id }, token);
              if (!res.ok) {
                setWsCreateError(res.error.message);
                return;
              }
              setWsRoles((prev) => [res.data, ...prev]);
              setShowWsCreate(false);
            } catch {
              setWsCreateError("Network error.");
            } finally {
              setWsCreateSubmitting(false);
            }
          }}
        />
      )}

      {/* Permissions panel (platform roles only for now) */}
      {permsPanelRole && isAuthenticated && (
        <PermissionsPanel
          roleId={permsPanelRole.id}
          roleName={permsPanelRole.name}
          accessToken={token}
          onClose={() => setPermsPanelRole(null)}
        />
      )}
    </>
  );
}
