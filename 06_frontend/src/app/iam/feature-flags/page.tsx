"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { Flag, Plus, ChevronDown, ChevronUp } from "lucide-react";
import {
  listFeatureFlags,
  createFeatureFlag,
  patchFeatureFlag,
  listFlagEnvironments,
  upsertFlagEnvironment,
  listFlagTargets,
  addFlagTarget,
  removeFlagTarget,
  evalFeatureFlag,
  listProducts,
  listCategories,
  type CategoryData,
} from "@/lib/api";
import { useAuth } from "@/components/providers/auth-provider";
import { PageHeader, PageBody } from "@/components/shell/page-header";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
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
  FeatureFlagData,
  FeatureFlagFilters,
  FlagEnvironmentData,
  FlagTargetData,
  FlagEvalResult,
  ProductData,
} from "@/types/api";

// ---------------------------------------------------------------------------
// Badge helpers
// ---------------------------------------------------------------------------

function ScopeBadge({ scope }: { scope: string }) {
  const cls =
    scope === "platform"
      ? "border-purple-400/30 bg-purple-500/10 text-purple-400"
      : scope === "org"
      ? "border-blue-400/30 bg-blue-500/10 text-blue-400"
      : "border-green-400/30 bg-green-500/10 text-green-400";
  return (
    <span className={`inline-flex items-center rounded-sm border px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${cls}`}>
      {scope}
    </span>
  );
}

function StatusBadge({ status }: { status: string }) {
  const variant =
    status === "active"
      ? "success"
      : status === "deprecated"
      ? "warning"
      : status === "archived"
      ? "danger"
      : "default";
  return <Badge variant={variant}>{status}</Badge>;
}

function FlagTypeBadge({ flag_type }: { flag_type: string }) {
  const cls =
    flag_type === "kill_switch"
      ? "border-[color:var(--danger)]/30 bg-[color:var(--danger-bg)] text-[color:var(--danger)]"
      : flag_type === "experiment"
      ? "border-orange-400/30 bg-orange-500/10 text-orange-400"
      : flag_type === "rollout"
      ? "border-[color:var(--info)]/30 bg-[color:var(--info-bg)] text-[color:var(--info)]"
      : "border-border bg-surface-2 text-foreground-muted";
  return (
    <span className={`inline-flex items-center rounded-sm border px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${cls}`}>
      {flag_type.replace("_", " ")}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Create Flag Modal
// ---------------------------------------------------------------------------

interface CreateFlagModalProps {
  products: ProductData[];
  flagCategories: CategoryData[];
  onSubmit: (body: {
    code: string;
    name: string;
    product_id: string;
    scope_id: number;
    category_id: number;
    flag_type: string;
    default_value?: unknown;
    status: string;
    description?: string;
  }) => Promise<void>;
  onClose: () => void;
  error: string | null;
  submitting: boolean;
}

function CreateFlagModal({
  products,
  flagCategories,
  onSubmit,
  onClose,
  error,
  submitting,
}: CreateFlagModalProps) {
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [productId, setProductId] = useState(products[0]?.id ?? "");
  const [scopeId, setScopeId] = useState(1);
  const [categoryId, setCategoryId] = useState<number | "">(flagCategories[0]?.id ?? "");
  const [flagType, setFlagType] = useState("boolean");
  const [defaultValue, setDefaultValue] = useState("false");
  const [status, setStatus] = useState("draft");
  const [description, setDescription] = useState("");
  const [valueError, setValueError] = useState<string | null>(null);
  const backdropRef = { current: null as HTMLDivElement | null };

  function deriveCode(v: string) {
    return v.toLowerCase().replace(/\s+/g, "_").replace(/[^a-z0-9_]/g, "");
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setValueError(null);
    if (!productId) {
      setValueError("Product is required.");
      return;
    }
    if (categoryId === "") {
      setValueError("Category is required.");
      return;
    }
    let parsed: unknown = defaultValue;
    try {
      parsed = JSON.parse(defaultValue);
    } catch {
      setValueError("Default value must be valid JSON (e.g. false, 0, \"text\", {...})");
      return;
    }
    await onSubmit({
      code,
      name,
      product_id: productId,
      scope_id: scopeId,
      category_id: categoryId as number,
      flag_type: flagType,
      default_value: parsed,
      status,
      description: description || undefined,
    });
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
      <div className="relative flex max-h-[90vh] w-full max-w-lg flex-col overflow-auto rounded-md border border-border bg-surface shadow-xl">
        <div className="flex shrink-0 items-center justify-between border-b border-border px-5 py-4">
          <h2 className="text-sm font-semibold">Create Feature Flag</h2>
          <button
            onClick={onClose}
            className="rounded-sm p-1 text-foreground-muted hover:bg-surface-3 hover:text-foreground"
          >
            ×
          </button>
        </div>
        <form onSubmit={handleSubmit} className="space-y-4 p-5">
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="ff-name">Name</Label>
              <Input
                id="ff-name"
                value={name}
                placeholder="Dark Mode"
                onChange={(e) => {
                  setName(e.target.value);
                  if (!code) setCode(deriveCode(e.target.value));
                }}
                required
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="ff-code">Code</Label>
              <Input
                id="ff-code"
                value={code}
                placeholder="dark_mode"
                className="font-mono"
                onChange={(e) => setCode(deriveCode(e.target.value))}
                required
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="ff-product">Product</Label>
            <select
              id="ff-product"
              value={productId}
              onChange={(e) => setProductId(e.target.value)}
              className="w-full rounded-md border border-border bg-surface-2 px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
              required
            >
              <option value="">— select product —</option>
              {products.map((p) => (
                <option key={p.id} value={p.id}>{p.name} ({p.code})</option>
              ))}
            </select>
          </div>

          <div className="grid grid-cols-3 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="ff-scope">Scope</Label>
              <select
                id="ff-scope"
                value={scopeId}
                onChange={(e) => setScopeId(Number(e.target.value))}
                className="w-full rounded-md border border-border bg-surface-2 px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
              >
                <option value={1}>platform</option>
                <option value={2}>org</option>
                <option value={3}>workspace</option>
              </select>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="ff-category">Category</Label>
              <select
                id="ff-category"
                value={categoryId}
                onChange={(e) => setCategoryId(e.target.value ? Number(e.target.value) : "")}
                className="w-full rounded-md border border-border bg-surface-2 px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
                required
              >
                <option value="">— select —</option>
                {flagCategories.map((c) => (
                  <option key={c.id} value={c.id}>{c.label}</option>
                ))}
              </select>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="ff-type">Flag Type</Label>
              <select
                id="ff-type"
                value={flagType}
                onChange={(e) => setFlagType(e.target.value)}
                className="w-full rounded-md border border-border bg-surface-2 px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
              >
                <option value="boolean">boolean</option>
                <option value="kill_switch">kill_switch</option>
                <option value="experiment">experiment</option>
                <option value="percentage">percentage</option>
                <option value="variant">variant</option>
              </select>
            </div>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="ff-default">Default Value (JSON)</Label>
            <Input
              id="ff-default"
              value={defaultValue}
              placeholder="false"
              className="font-mono"
              onChange={(e) => setDefaultValue(e.target.value)}
            />
            {valueError && (
              <p className="text-xs text-[color:var(--danger)]">{valueError}</p>
            )}
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="ff-status">Status</Label>
            <select
              id="ff-status"
              value={status}
              onChange={(e) => setStatus(e.target.value)}
              className="w-full rounded-md border border-border bg-surface-2 px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
            >
              <option value="draft">draft</option>
              <option value="active">active</option>
              <option value="deprecated">deprecated</option>
              <option value="archived">archived</option>
            </select>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="ff-desc">
              Description <span className="text-foreground-subtle">(optional)</span>
            </Label>
            <Input
              id="ff-desc"
              value={description}
              placeholder="Short description"
              onChange={(e) => setDescription(e.target.value)}
            />
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
              {submitting ? "Creating…" : "Create Flag"}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Flag Detail Panel (expanded row)
// ---------------------------------------------------------------------------

interface FlagDetailProps {
  flag: FeatureFlagData;
  accessToken: string;
  onClose: () => void;
}

function FlagDetail({ flag, accessToken, onClose }: FlagDetailProps) {
  const [envs, setEnvs] = useState<FlagEnvironmentData[]>([]);
  const [targets, setTargets] = useState<FlagTargetData[]>([]);
  const [loading, setLoading] = useState(true);

  // Eval tester
  const [evalUserId, setEvalUserId] = useState("");
  const [evalOrgId, setEvalOrgId] = useState("");
  const [evalWsId, setEvalWsId] = useState("");
  const [evalEnv, setEvalEnv] = useState("dev");
  const [evalResult, setEvalResult] = useState<FlagEvalResult | null>(null);
  const [evalError, setEvalError] = useState<string | null>(null);
  const [evaling, setEvaling] = useState(false);

  // Add target
  const [newTargetType, setNewTargetType] = useState("org");
  const [newTargetId, setNewTargetId] = useState("");
  const [addingTarget, setAddingTarget] = useState(false);
  const [targetError, setTargetError] = useState<string | null>(null);

  const backdropRef = { current: null as HTMLDivElement | null };

  useEffect(() => {
    setLoading(true);
    Promise.all([
      listFlagEnvironments(flag.id, accessToken),
      listFlagTargets(flag.id, accessToken),
    ])
      .then(([envRes, targetRes]) => {
        if (envRes.ok) setEnvs(envRes.data.items);
        if (targetRes.ok) setTargets(targetRes.data.items);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [flag.id, accessToken]);

  async function handleEnvToggle(env: FlagEnvironmentData) {
    try {
      const res = await upsertFlagEnvironment(
        flag.id,
        env.environment,
        { enabled: !env.enabled, value: env.value },
        accessToken
      );
      if (res.ok) {
        setEnvs((prev) =>
          prev.map((e) => (e.id === env.id ? res.data : e))
        );
      }
    } catch {
      // silent
    }
  }

  async function handleAddTarget(e: React.FormEvent) {
    e.preventDefault();
    if (!newTargetId.trim()) return;
    setTargetError(null);
    setAddingTarget(true);
    try {
      const res = await addFlagTarget(
        flag.id,
        { target_type: newTargetType, target_id: newTargetId.trim(), enabled: true },
        accessToken
      );
      if (!res.ok) { setTargetError(res.error.message); return; }
      setTargets((prev) => [res.data, ...prev]);
      setNewTargetId("");
    } catch {
      setTargetError("Network error.");
    } finally {
      setAddingTarget(false);
    }
  }

  async function handleRemoveTarget(targetId: string) {
    try {
      await removeFlagTarget(flag.id, targetId, accessToken);
      setTargets((prev) => prev.filter((t) => t.id !== targetId));
    } catch {
      // silent
    }
  }

  async function handleEval(e: React.FormEvent) {
    e.preventDefault();
    setEvalError(null);
    setEvalResult(null);
    setEvaling(true);
    try {
      const res = await evalFeatureFlag(
        {
          flag_code: flag.code,
          user_id: evalUserId || undefined,
          org_id: evalOrgId || undefined,
          workspace_id: evalWsId || undefined,
          environment: evalEnv,
        },
        accessToken
      );
      if (!res.ok) { setEvalError(res.error.message); return; }
      setEvalResult(res.data);
    } catch {
      setEvalError("Network error.");
    } finally {
      setEvaling(false);
    }
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
      <div className="relative flex h-[90vh] w-full max-w-3xl flex-col rounded-md border border-border bg-surface shadow-xl">
        {/* Header */}
        <div className="flex shrink-0 items-center justify-between border-b border-border px-5 py-4">
          <div className="space-y-0.5">
            <div className="flex items-center gap-2">
              <h2 className="text-sm font-semibold">{flag.name}</h2>
              <span className="font-mono text-xs text-foreground-muted">{flag.code}</span>
            </div>
            <div className="flex items-center gap-2">
              <ScopeBadge scope={flag.scope_code ?? ""} />
              <FlagTypeBadge flag_type={flag.flag_type} />
              <StatusBadge status={flag.status} />
            </div>
          </div>
          <button
            onClick={onClose}
            className="rounded-sm p-1 text-foreground-muted hover:bg-surface-3 hover:text-foreground"
          >
            ×
          </button>
        </div>

        <div className="min-h-0 flex-1 overflow-auto p-5 space-y-6">
          {loading ? (
            <div className="space-y-2">
              {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-8 w-full" />)}
            </div>
          ) : (
            <>
              {/* Basic info */}
              <div>
                <p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-foreground-muted">Info</p>
                <div className="grid grid-cols-2 gap-3 text-xs">
                  <div>
                    <span className="text-foreground-muted">Default Value: </span>
                    <code className="font-mono">{JSON.stringify(flag.default_value)}</code>
                  </div>
                  <div>
                    <span className="text-foreground-muted">Category: </span>
                    {flag.category_label ?? flag.category_code ?? "—"}
                  </div>
                  {flag.product_name && (
                    <div>
                      <span className="text-foreground-muted">Product: </span>
                      {flag.product_name}
                    </div>
                  )}
                </div>
              </div>

              {/* Environments */}
              <div>
                <p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-foreground-muted">
                  Environment Overrides
                </p>
                {envs.length === 0 ? (
                  <p className="text-xs text-foreground-muted">No environment overrides configured.</p>
                ) : (
                  <div className="space-y-2">
                    {envs.map((env) => (
                      <div
                        key={env.id}
                        className="flex items-center justify-between rounded-md border border-border bg-surface-2 px-3 py-2"
                      >
                        <span className="text-xs font-medium capitalize">{env.environment}</span>
                        <div className="flex items-center gap-3">
                          <code className="text-xs text-foreground-muted">
                            {JSON.stringify(env.value)}
                          </code>
                          <button
                            onClick={() => handleEnvToggle(env)}
                            className={`relative inline-flex h-4 w-8 items-center rounded-full transition-colors ${
                              env.enabled ? "bg-[color:var(--success)]" : "bg-border"
                            }`}
                          >
                            <span
                              className={`inline-block h-3 w-3 transform rounded-full bg-white transition-transform ${
                                env.enabled ? "translate-x-4" : "translate-x-0.5"
                              }`}
                            />
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Targets */}
              {(flag.scope_code === "org" || flag.scope_code === "workspace") && (
                <div>
                  <p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-foreground-muted">
                    {flag.scope_code === "org" ? "Org Targets" : "Workspace Targets"}
                  </p>
                  <form onSubmit={handleAddTarget} className="mb-3 flex gap-2">
                    <select
                      value={newTargetType}
                      onChange={(e) => setNewTargetType(e.target.value)}
                      className="rounded-md border border-border bg-surface-2 px-2 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-ring"
                    >
                      <option value="org">org</option>
                      <option value="workspace">workspace</option>
                      <option value="user">user</option>
                    </select>
                    <Input
                      value={newTargetId}
                      onChange={(e) => setNewTargetId(e.target.value)}
                      placeholder="Target ID…"
                      className="font-mono text-xs"
                    />
                    <Button type="submit" size="sm" disabled={addingTarget || !newTargetId.trim()}>
                      {addingTarget ? "Adding…" : "Add"}
                    </Button>
                  </form>
                  {targetError && (
                    <p className="mb-2 text-xs text-[color:var(--danger)]">{targetError}</p>
                  )}
                  {targets.length === 0 ? (
                    <p className="text-xs text-foreground-muted">No targets yet.</p>
                  ) : (
                    <div className="space-y-1.5">
                      {targets.map((t) => (
                        <div
                          key={t.id}
                          className="flex items-center justify-between rounded-md border border-border bg-surface-2 px-3 py-1.5 text-xs"
                        >
                          <div className="flex items-center gap-2">
                            <Badge variant="outline">{t.target_type}</Badge>
                            <code className="font-mono text-foreground-muted">{t.target_id}</code>
                          </div>
                          <button
                            onClick={() => handleRemoveTarget(t.id)}
                            className="text-[color:var(--danger)] hover:opacity-70"
                          >
                            ×
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* Eval tester */}
              <div>
                <p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-foreground-muted">
                  Eval Tester
                </p>
                <form onSubmit={handleEval} className="space-y-3">
                  <div className="grid grid-cols-2 gap-3">
                    <div className="space-y-1">
                      <Label className="text-[10px]">User ID (optional)</Label>
                      <Input value={evalUserId} onChange={(e) => setEvalUserId(e.target.value)} className="font-mono text-xs" placeholder="usr_…" />
                    </div>
                    <div className="space-y-1">
                      <Label className="text-[10px]">Org ID (optional)</Label>
                      <Input value={evalOrgId} onChange={(e) => setEvalOrgId(e.target.value)} className="font-mono text-xs" placeholder="org_…" />
                    </div>
                    <div className="space-y-1">
                      <Label className="text-[10px]">Workspace ID (optional)</Label>
                      <Input value={evalWsId} onChange={(e) => setEvalWsId(e.target.value)} className="font-mono text-xs" placeholder="ws_…" />
                    </div>
                    <div className="space-y-1">
                      <Label className="text-[10px]">Environment</Label>
                      <select
                        value={evalEnv}
                        onChange={(e) => setEvalEnv(e.target.value)}
                        className="w-full rounded-md border border-border bg-surface-2 px-2 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-ring"
                      >
                        <option value="dev">dev</option>
                        <option value="staging">staging</option>
                        <option value="prod">prod</option>
                      </select>
                    </div>
                  </div>
                  <Button type="submit" size="sm" disabled={evaling}>
                    {evaling ? "Evaluating…" : "Evaluate"}
                  </Button>
                </form>

                {evalError && (
                  <p className="mt-2 text-xs text-[color:var(--danger)]">{evalError}</p>
                )}

                {evalResult && (
                  <div className="mt-3 rounded-md border border-[color:var(--success)]/30 bg-[color:var(--success-bg)] px-4 py-3">
                    <div className="flex items-center gap-2">
                      <span className="text-sm">✅</span>
                      <span className="text-sm font-semibold">Evaluated</span>
                    </div>
                    <div className="mt-1.5 space-y-0.5 text-xs text-foreground-muted">
                      <div>Value: <code className="font-mono">{JSON.stringify(evalResult.value)}</code></div>
                      <div>Reason: <span className="font-medium">{evalResult.reason}</span></div>
                    </div>
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function FeatureFlagsPage() {
  const auth = useAuth();
  const router = useRouter();

  const isAuthenticated = auth.status === "authenticated";
  const token = isAuthenticated ? auth.accessToken : "";

  const [flags, setFlags] = useState<FeatureFlagData[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [filterScopeId, setFilterScopeId] = useState<number | "">("");
  const [filterStatus, setFilterStatus] = useState("");
  const [filterFlagType, setFilterFlagType] = useState("");
  const [filterProductId, setFilterProductId] = useState("");

  // Products (for filter/create)
  const [products, setProducts] = useState<ProductData[]>([]);
  const [flagCategories, setFlagCategories] = useState<CategoryData[]>([]);

  // Create modal
  const [showCreate, setShowCreate] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [createSubmitting, setCreateSubmitting] = useState(false);

  // Detail panel
  const [selectedFlag, setSelectedFlag] = useState<FeatureFlagData | null>(null);

  const fetchFlags = useCallback(
    (filters: FeatureFlagFilters = {}) => {
      if (!token) return;
      setLoading(true);
      listFeatureFlags(token, filters)
        .then((res) => {
          if (res.ok) { setFlags(res.data.items); setTotal(res.data.total); }
          else setError(res.error.message);
        })
        .catch(() => setError("Network error."))
        .finally(() => setLoading(false));
    },
    [token]
  );

  useEffect(() => {
    if (auth.status !== "authenticated") return;
    fetchFlags({
      scope_id: typeof filterScopeId === "number" ? filterScopeId : undefined,
      status: filterStatus || undefined,
      flag_type: filterFlagType || undefined,
      product_id: filterProductId || undefined,
    });
    // Load products for dropdowns
    listProducts(token, { limit: 100 })
      .then((res) => { if (res.ok) setProducts(res.data.items); })
      .catch(() => {});
    // Load flag categories
    listCategories(token, "flag")
      .then((res) => { if (res.ok) setFlagCategories(res.data.items); })
      .catch(() => {});
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [auth.status, filterScopeId, filterStatus, filterFlagType, filterProductId]);

  async function handleToggleActive(flag: FeatureFlagData) {
    try {
      const res = await patchFeatureFlag(flag.id, { is_active: !flag.is_active }, token);
      if (res.ok) {
        setFlags((prev) => prev.map((f) => (f.id === flag.id ? res.data : f)));
      }
    } catch {
      // silent
    }
  }

  if (auth.status === "loading") {
    return (
      <>
        <PageHeader breadcrumb={["IAM", "Feature Flags"]} title="Feature Flags" description="Manage flag lifecycle, targets, and environment overrides." />
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
        <PageHeader breadcrumb={["IAM", "Feature Flags"]} title="Feature Flags" description="Manage flag lifecycle, targets, and environment overrides." />
        <PageBody>
          <Card>
            <EmptyState
              icon={<Flag />}
              title="Sign in required"
              description="Sign in to view feature flags."
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
        breadcrumb={["IAM", "Feature Flags"]}
        title="Feature Flags"
        description="Manage flag lifecycle, environment overrides, targets, and evaluations."
        actions={
          <Button size="sm" onClick={() => setShowCreate(true)}>
            <Plus className="size-3.5" />
            New Flag
          </Button>
        }
      />

      <PageBody>
        {/* Filters */}
        <div className="mb-4 flex flex-wrap items-center gap-2">
          <select
            value={filterScopeId}
            onChange={(e) => setFilterScopeId(e.target.value ? Number(e.target.value) : "")}
            className="rounded-md border border-border bg-surface-2 px-2 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-ring"
          >
            <option value="">All Scopes</option>
            <option value={1}>platform</option>
            <option value={2}>org</option>
            <option value={3}>workspace</option>
          </select>
          <select
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value)}
            className="rounded-md border border-border bg-surface-2 px-2 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-ring"
          >
            <option value="">All Statuses</option>
            <option value="draft">draft</option>
            <option value="active">active</option>
            <option value="deprecated">deprecated</option>
            <option value="archived">archived</option>
          </select>
          <select
            value={filterFlagType}
            onChange={(e) => setFilterFlagType(e.target.value)}
            className="rounded-md border border-border bg-surface-2 px-2 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-ring"
          >
            <option value="">All Types</option>
            <option value="boolean">boolean</option>
            <option value="kill_switch">kill_switch</option>
            <option value="experiment">experiment</option>
            <option value="percentage">percentage</option>
            <option value="variant">variant</option>
          </select>
          <select
            value={filterProductId}
            onChange={(e) => setFilterProductId(e.target.value)}
            className="rounded-md border border-border bg-surface-2 px-2 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-ring"
          >
            <option value="">All Products</option>
            {products.map((p) => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </select>
          {(filterScopeId !== "" || filterStatus || filterFlagType || filterProductId) && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                setFilterScopeId("");
                setFilterStatus("");
                setFilterFlagType("");
                setFilterProductId("");
              }}
            >
              Clear filters
            </Button>
          )}
        </div>

        <Card>
          <CardHeader>
            <CardTitle>
              Feature Flags
              {total > 0 && (
                <span className="ml-2 font-normal text-foreground-muted">({total})</span>
              )}
            </CardTitle>
          </CardHeader>

          {loading && (
            <div className="space-y-2 p-4">
              {[...Array(5)].map((_, i) => <Skeleton key={i} className="h-8 w-full" />)}
            </div>
          )}

          {!loading && error && (
            <EmptyState
              icon={<Flag />}
              title="Could not load flags"
              description={error}
              action={<Button size="sm" variant="outline" onClick={() => fetchFlags()}>Retry</Button>}
            />
          )}

          {!loading && !error && flags.length === 0 && (
            <EmptyState
              icon={<Flag />}
              title="No flags yet"
              description="Create the first feature flag."
              action={
                <Button size="sm" onClick={() => setShowCreate(true)}>
                  <Plus className="size-3.5" />
                  New Flag
                </Button>
              }
            />
          )}

          {!loading && !error && flags.length > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Code</TableHead>
                  <TableHead>Product</TableHead>
                  <TableHead>Scope</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Active</TableHead>
                  <TableHead className="w-10" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {flags.map((f) => (
                  <TableRow key={f.id} className="cursor-pointer hover:bg-surface-2" onClick={() => setSelectedFlag(f)}>
                    <TableCell className="font-medium">{f.name}</TableCell>
                    <TableCell className="font-mono text-[11px] text-foreground-muted">{f.code}</TableCell>
                    <TableCell className="text-xs text-foreground-muted">
                      {f.product_name ?? "—"}
                    </TableCell>
                    <TableCell>
                      <ScopeBadge scope={f.scope_code ?? ""} />
                    </TableCell>
                    <TableCell>
                      <FlagTypeBadge flag_type={f.flag_type} />
                    </TableCell>
                    <TableCell>
                      <StatusBadge status={f.status} />
                    </TableCell>
                    <TableCell onClick={(e) => e.stopPropagation()}>
                      <button
                        onClick={() => handleToggleActive(f)}
                        className={`relative inline-flex h-4 w-8 items-center rounded-full transition-colors ${
                          f.is_active ? "bg-[color:var(--success)]" : "bg-border"
                        }`}
                        title={f.is_active ? "Deactivate" : "Activate"}
                      >
                        <span
                          className={`inline-block h-3 w-3 transform rounded-full bg-white transition-transform ${
                            f.is_active ? "translate-x-4" : "translate-x-0.5"
                          }`}
                        />
                      </button>
                    </TableCell>
                    <TableCell onClick={(e) => e.stopPropagation()}>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => setSelectedFlag(selectedFlag?.id === f.id ? null : f)}
                      >
                        {selectedFlag?.id === f.id ? (
                          <ChevronUp className="size-3.5 text-foreground-muted" />
                        ) : (
                          <ChevronDown className="size-3.5 text-foreground-muted" />
                        )}
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </Card>
      </PageBody>

      {/* Create modal */}
      {showCreate && (
        <CreateFlagModal
          products={products}
          flagCategories={flagCategories}
          error={createError}
          submitting={createSubmitting}
          onClose={() => { setShowCreate(false); setCreateError(null); }}
          onSubmit={async (body) => {
            setCreateError(null);
            setCreateSubmitting(true);
            try {
              const res = await createFeatureFlag(body, token);
              if (!res.ok) { setCreateError(res.error.message); return; }
              setFlags((prev) => [res.data, ...prev]);
              setTotal((t) => t + 1);
              setShowCreate(false);
            } catch {
              setCreateError("Network error.");
            } finally {
              setCreateSubmitting(false);
            }
          }}
        />
      )}

      {/* Detail panel */}
      {selectedFlag && isAuthenticated && (
        <FlagDetail
          flag={selectedFlag}
          accessToken={token}
          onClose={() => setSelectedFlag(null)}
        />
      )}
    </>
  );
}
