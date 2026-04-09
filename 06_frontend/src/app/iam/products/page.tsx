"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Package, Plus } from "lucide-react";
import { listProducts } from "@/lib/api";
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
import { CreateProductModal } from "@/features/iam/_components/create-product-modal";
import type { ProductData } from "@/types/api";

export default function IamProductsPage() {
  const auth = useAuth();
  const router = useRouter();

  const [products, setProducts] = useState<ProductData[] | null>(null);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);

  useEffect(() => {
    if (auth.status === "loading") return;
    if (auth.status === "unauthenticated") {
      setError("unauthenticated");
      setLoading(false);
      return;
    }
    fetchProducts();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [auth.status]);

  function fetchProducts() {
    if (auth.status !== "authenticated") return;
    setLoading(true);
    listProducts(auth.accessToken)
      .then((res) => {
        if (res.ok) {
          setProducts(res.data.items);
          setTotal(res.data.total);
        } else {
          setError(res.error.message);
        }
      })
      .catch(() => setError("Network error."))
      .finally(() => setLoading(false));
  }

  const isAuthenticated = auth.status === "authenticated";

  return (
    <>
      <PageHeader
        breadcrumb={["IAM", "Products"]}
        title="Products"
        description="Catalogue of sellable and internal platform products."
        actions={
          isAuthenticated ? (
            <Button size="sm" onClick={() => setShowCreate(true)}>
              <Plus className="size-3.5" />
              New Product
            </Button>
          ) : undefined
        }
      />

      <PageBody>
        <Card>
          <CardHeader>
            <CardTitle>
              All Products
              {total > 0 && (
                <span className="ml-2 font-normal text-foreground-muted">({total})</span>
              )}
            </CardTitle>
          </CardHeader>

          {(loading || auth.status === "loading") && (
            <div className="space-y-2 p-4">
              {[...Array(5)].map((_, i) => (
                <Skeleton key={i} className="h-8 w-full" />
              ))}
            </div>
          )}

          {!loading && error === "unauthenticated" && (
            <EmptyState
              icon={<Package />}
              title="Sign in required"
              description="Sign in to view products."
              action={
                <Button size="sm" onClick={() => router.push("/iam")}>
                  Go to sign in
                </Button>
              }
            />
          )}

          {!loading && error && error !== "unauthenticated" && (
            <EmptyState
              icon={<Package />}
              title="Could not load products"
              description={error}
              action={
                <Button size="sm" variant="outline" onClick={fetchProducts}>
                  Retry
                </Button>
              }
            />
          )}

          {!loading && !error && (!products || products.length === 0) && (
            <EmptyState
              icon={<Package />}
              title="No products yet"
              description="Create your first product to build the subscription catalogue."
              action={
                isAuthenticated ? (
                  <Button size="sm" onClick={() => setShowCreate(true)}>
                    <Plus className="size-3.5" />
                    New Product
                  </Button>
                ) : undefined
              }
            />
          )}

          {!loading && !error && products && products.length > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Code</TableHead>
                  <TableHead>Category</TableHead>
                  <TableHead>Sellable</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Description</TableHead>
                  <TableHead>Created</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {products.map((p) => (
                  <TableRow key={p.id}>
                    <TableCell className="font-medium">{p.name}</TableCell>
                    <TableCell className="font-mono text-[11px] text-foreground-muted">
                      {p.code}
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline">{p.category_label ?? p.category_code ?? "—"}</Badge>
                    </TableCell>
                    <TableCell>
                      {p.is_sellable ? (
                        <Badge variant="success">yes</Badge>
                      ) : (
                        <Badge variant="default">no</Badge>
                      )}
                    </TableCell>
                    <TableCell>
                      {p.is_active ? (
                        <Badge variant="success">active</Badge>
                      ) : (
                        <Badge variant="default">inactive</Badge>
                      )}
                    </TableCell>
                    <TableCell className="max-w-[200px] truncate text-xs text-foreground-muted">
                      {p.description ?? "—"}
                    </TableCell>
                    <TableCell className="font-mono text-[11px] text-foreground-muted">
                      {new Date(p.created_at).toLocaleDateString()}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </Card>
      </PageBody>

      {showCreate && auth.status === "authenticated" && (
        <CreateProductModal
          accessToken={auth.accessToken}
          onCreated={(product) => {
            setProducts((prev) => (prev ? [product, ...prev] : [product]));
            setTotal((t) => t + 1);
            setShowCreate(false);
          }}
          onClose={() => setShowCreate(false)}
        />
      )}
    </>
  );
}
