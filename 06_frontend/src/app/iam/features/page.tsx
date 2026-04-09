"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Flag, X } from "lucide-react";
import { listFeatures, listCategories, type CategoryData } from "@/lib/api";
import { useAuth } from "@/components/providers/auth-provider";
import { PageHeader, PageBody } from "@/components/shell/page-header";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from "@/components/ui/table";
import type { FeatureData, FeatureFilters } from "@/types/api";

// -----------------------------------------------------------------------
// Filter bar
// -----------------------------------------------------------------------

interface FilterBarProps {
  filters: FeatureFilters;
  categories: CategoryData[];
  onChange: (f: FeatureFilters) => void;
}

// Scopes are a fixed dim table: 1=platform, 2=org, 3=workspace
const SCOPES: { id: number; label: string }[] = [
  { id: 1, label: "platform" },
  { id: 2, label: "org" },
  { id: 3, label: "workspace" },
];

function FilterBar({ filters, categories, onChange }: FilterBarProps) {
  const hasFilters = filters.scope_id != null || filters.category_id != null;

  return (
    <div className="flex flex-wrap items-center gap-2 border-b border-border px-4 py-3">
      <span className="text-xs font-medium text-foreground-muted">Filter:</span>

      <select
        value={filters.scope_id ?? ""}
        onChange={(e) => onChange({ ...filters, scope_id: e.target.value ? Number(e.target.value) : undefined })}
        className="h-7 rounded-sm border border-border bg-surface px-2 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
      >
        <option value="">All scopes</option>
        {SCOPES.map((s) => (
          <option key={s.id} value={s.id}>{s.label}</option>
        ))}
      </select>

      <select
        value={filters.category_id ?? ""}
        onChange={(e) => onChange({ ...filters, category_id: e.target.value ? Number(e.target.value) : undefined })}
        className="h-7 rounded-sm border border-border bg-surface px-2 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
      >
        <option value="">All categories</option>
        {categories.map((c) => (
          <option key={c.id} value={c.id}>{c.label}</option>
        ))}
      </select>

      {hasFilters && (
        <button
          onClick={() => onChange({})}
          className="flex items-center gap-1 rounded-sm border border-border px-2 py-1 text-xs text-foreground-muted hover:bg-surface-3"
        >
          <X className="size-3" />
          Clear
        </button>
      )}
    </div>
  );
}

// -----------------------------------------------------------------------
// Page
// -----------------------------------------------------------------------

export default function IamFeaturesPage() {
  const auth = useAuth();
  const router = useRouter();

  const [features, setFeatures] = useState<FeatureData[] | null>(null);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFilters] = useState<FeatureFilters>({});
  const [categories, setCategories] = useState<CategoryData[]>([]);

  useEffect(() => {
    if (auth.status === "loading") return;
    if (auth.status === "unauthenticated") {
      setError("unauthenticated");
      setLoading(false);
      return;
    }
    fetchFeatures(filters);
    listCategories(auth.accessToken, "feature").then((res) => {
      if (res.ok) setCategories(res.data.items);
    });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [auth.status, filters]);

  function fetchFeatures(f: FeatureFilters) {
    if (auth.status !== "authenticated") return;
    setLoading(true);
    listFeatures(auth.accessToken, f)
      .then((res) => {
        if (res.ok) {
          setFeatures(res.data.items);
          setTotal(res.data.total);
        } else {
          setError(res.error.message);
        }
      })
      .catch(() => setError("Network error."))
      .finally(() => setLoading(false));
  }

  function handleFilterChange(f: FeatureFilters) {
    setFilters(f);
  }

  const isAuthenticated = auth.status === "authenticated";

  return (
    <>
      <PageHeader
        breadcrumb={["IAM", "Feature Registry"]}
        title="Feature Registry"
        description="Read-only view of all registered platform features. Features are registered via API or migration."
      />

      <PageBody>
        <Card>
          <CardHeader>
            <CardTitle>
              All Features
              {total > 0 && (
                <span className="ml-2 font-normal text-foreground-muted">({total})</span>
              )}
            </CardTitle>
          </CardHeader>

          {isAuthenticated && (
            <FilterBar filters={filters} categories={categories} onChange={handleFilterChange} />
          )}

          {(loading || auth.status === "loading") && (
            <div className="space-y-2 p-4">
              {[...Array(6)].map((_, i) => (
                <Skeleton key={i} className="h-8 w-full" />
              ))}
            </div>
          )}

          {!loading && error === "unauthenticated" && (
            <EmptyState
              icon={<Flag />}
              title="Sign in required"
              description="Sign in to view the feature registry."
              action={
                <Button size="sm" onClick={() => router.push("/iam")}>
                  Go to sign in
                </Button>
              }
            />
          )}

          {!loading && error && error !== "unauthenticated" && (
            <EmptyState
              icon={<Flag />}
              title="Could not load features"
              description={error}
              action={
                <Button size="sm" variant="outline" onClick={() => fetchFeatures(filters)}>
                  Retry
                </Button>
              }
            />
          )}

          {!loading && !error && (!features || features.length === 0) && (
            <EmptyState
              icon={<Flag />}
              title="No features registered"
              description="Features are registered via API or database migration — none found with current filters."
            />
          )}

          {!loading && !error && features && features.length > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Code</TableHead>
                  <TableHead>Name</TableHead>
                  <TableHead>Scope</TableHead>
                  <TableHead>Category</TableHead>
                  <TableHead>Product</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Description</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {features.map((f) => (
                  <TableRow key={f.id}>
                    <TableCell className="font-mono text-[11px]">{f.code}</TableCell>
                    <TableCell className="font-medium">{f.name}</TableCell>
                    <TableCell>
                      <Badge variant={
                        f.scope_code === "platform" ? "info"
                        : f.scope_code === "org" ? "warning"
                        : "outline"
                      }>
                        {f.scope_label ?? f.scope_code ?? "—"}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline">{f.category_label ?? f.category_code ?? "—"}</Badge>
                    </TableCell>
                    <TableCell className="font-mono text-[11px] text-foreground-muted">
                      {f.product_id ? f.product_id.slice(0, 8) : <span className="text-foreground-subtle">—</span>}
                    </TableCell>
                    <TableCell>
                      {f.is_active ? (
                        <Badge variant="success">active</Badge>
                      ) : (
                        <Badge variant="default">inactive</Badge>
                      )}
                    </TableCell>
                    <TableCell className="max-w-[220px] truncate text-xs text-foreground-muted">
                      {f.description ?? "—"}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </Card>
      </PageBody>
    </>
  );
}
