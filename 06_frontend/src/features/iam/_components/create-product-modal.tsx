"use client";

import { useEffect, useState, useRef } from "react";
import { X } from "lucide-react";
import { createProduct, listCategories, type CategoryData } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { ProductData } from "@/types/api";

interface CreateProductModalProps {
  accessToken: string;
  onCreated: (product: ProductData) => void;
  onClose: () => void;
}

export function CreateProductModal({ accessToken, onCreated, onClose }: CreateProductModalProps) {
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [categories, setCategories] = useState<CategoryData[]>([]);
  const [categoryId, setCategoryId] = useState<number | null>(null);
  const [isSellable, setIsSellable] = useState(true);

  useEffect(() => {
    listCategories(accessToken, "product").then((res) => {
      if (res.ok) {
        setCategories(res.data.items);
        if (res.data.items.length > 0) setCategoryId(res.data.items[0].id);
      }
    });
  }, [accessToken]);
  const [description, setDescription] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const backdropRef = useRef<HTMLDivElement>(null);

  function deriveCode(v: string): string {
    return v.toLowerCase().replace(/\s+/g, "_").replace(/[^a-z0-9_]/g, "");
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (categoryId == null) {
      setError("Select a category.");
      return;
    }
    setSubmitting(true);
    try {
      const res = await createProduct(
        { name, code, category_id: categoryId, is_sellable: isSellable, description: description || undefined },
        accessToken
      );
      if (!res.ok) {
        setError(res.error.message);
        return;
      }
      onCreated(res.data);
    } catch {
      setError("Network error.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div
      ref={backdropRef}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      onClick={(e) => { if (e.target === backdropRef.current) onClose(); }}
    >
      <div className="relative w-full max-w-md rounded-md border border-border bg-surface shadow-xl">
        <div className="flex items-center justify-between border-b border-border px-5 py-4">
          <h2 className="text-sm font-semibold">Create Product</h2>
          <button
            onClick={onClose}
            className="rounded-sm p-1 text-foreground-muted hover:bg-surface-3 hover:text-foreground"
            aria-label="Close"
          >
            <X className="size-4" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4 p-5">
          <div className="space-y-1.5">
            <Label htmlFor="product-name">Name</Label>
            <Input
              id="product-name"
              value={name}
              placeholder="IAM Core"
              onChange={(e) => {
                setName(e.target.value);
                if (!code) setCode(deriveCode(e.target.value));
              }}
              required
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="product-code">Code</Label>
            <Input
              id="product-code"
              value={code}
              placeholder="iam_core"
              onChange={(e) => setCode(deriveCode(e.target.value))}
              required
              className="font-mono"
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="product-category">Category</Label>
            <select
              id="product-category"
              value={categoryId ?? ""}
              onChange={(e) => setCategoryId(e.target.value ? Number(e.target.value) : null)}
              className="flex h-9 w-full rounded-md border border-border bg-surface px-3 py-1 text-sm text-foreground focus-visible:outline-none focus-visible:border-border-strong focus-visible:ring-1 focus-visible:ring-ring"
            >
              {categories.map((c) => (
                <option key={c.id} value={c.id}>{c.label}</option>
              ))}
            </select>
          </div>

          <div className="flex items-center gap-3">
            <input
              id="product-sellable"
              type="checkbox"
              checked={isSellable}
              onChange={(e) => setIsSellable(e.target.checked)}
              className="size-4 rounded border-border accent-foreground"
            />
            <Label htmlFor="product-sellable" className="cursor-pointer">
              Sellable (appears in subscription catalogue)
            </Label>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="product-description">
              Description <span className="text-foreground-subtle">(optional)</span>
            </Label>
            <Input
              id="product-description"
              value={description}
              placeholder="Short description of this product"
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
              {submitting ? "Creating…" : "Create Product"}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
