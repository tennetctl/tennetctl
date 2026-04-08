"use client";

import { useEffect, useState } from "react";
import { getVaultStatus } from "@/lib/api";
import type { VaultStatus } from "@/types/api";

export default function VaultPage() {
  const [status, setStatus] = useState<VaultStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getVaultStatus()
      .then((res) => {
        if (res.ok) {
          setStatus(res.data);
        } else {
          setError(res.error.message);
        }
      })
      .catch(() => setError("Network error — is the backend running?"))
      .finally(() => setLoading(false));
  }, []);

  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-8">
      <div className="w-full max-w-md">
        <h1 className="text-2xl font-bold mb-6">Vault Status</h1>

        {loading && (
          <p className="text-neutral-400 text-sm">Loading…</p>
        )}

        {error && (
          <div className="rounded-md bg-red-900/30 border border-red-800 px-4 py-3 text-sm text-red-300">
            {error}
          </div>
        )}

        {status && (
          <div className="rounded-md border border-white/10 bg-white/5 overflow-hidden">
            <div className="px-4 py-3 border-b border-white/10 flex items-center justify-between">
              <span className="text-sm font-medium">Vault</span>
              <span
                className={[
                  "rounded-full px-2 py-0.5 text-xs font-medium",
                  status.status === "unsealed"
                    ? "bg-green-900/40 text-green-300 border border-green-800"
                    : "bg-red-900/40 text-red-300 border border-red-800",
                ].join(" ")}
              >
                {status.status}
              </span>
            </div>

            <dl className="divide-y divide-white/10 text-sm">
              <Row label="Initialized" value={status.initialized ? "Yes" : "No"} />
              <Row label="Unseal mode" value={status.unseal_mode} />
              <Row
                label="Initialized at"
                value={
                  status.initialized_at
                    ? new Date(status.initialized_at).toLocaleString()
                    : "—"
                }
              />
            </dl>
          </div>
        )}

        <div className="mt-6 flex gap-4 text-sm">
          <a href="/" className="text-neutral-400 hover:text-white transition">
            ← Home
          </a>
          <a href="/iam" className="text-neutral-400 hover:text-white transition">
            Sign in →
          </a>
        </div>
      </div>
    </main>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between px-4 py-2.5">
      <dt className="text-neutral-400">{label}</dt>
      <dd className="font-mono text-xs">{value}</dd>
    </div>
  );
}
