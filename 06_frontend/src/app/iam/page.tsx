"use client";

import { useState } from "react";
import { login, tokenStore } from "@/lib/api";
import type { ApiError } from "@/types/api";

export default function IamPage() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    setLoading(true);

    try {
      const result = await login(username, password);
      if (result.ok) {
        tokenStore.set(result.data);
        setSuccess(`Logged in as ${username}. Session: ${result.data.session_id.slice(0, 8)}…`);
      } else {
        setError((result as ApiError).error.message);
      }
    } catch (err) {
      setError("Network error — is the backend running?");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-8">
      <div className="w-full max-w-sm">
        <h1 className="text-2xl font-bold mb-6">Sign in</h1>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div className="flex flex-col gap-1">
            <label htmlFor="username" className="text-sm text-neutral-400">
              Username
            </label>
            <input
              id="username"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="admin"
              required
              className="rounded-md border border-white/20 bg-white/5 px-3 py-2 text-sm outline-none focus:border-white/40"
            />
          </div>

          <div className="flex flex-col gap-1">
            <label htmlFor="password" className="text-sm text-neutral-400">
              Password
            </label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              required
              className="rounded-md border border-white/20 bg-white/5 px-3 py-2 text-sm outline-none focus:border-white/40"
            />
          </div>

          {error && (
            <p className="rounded-md bg-red-900/30 border border-red-800 px-3 py-2 text-sm text-red-300">
              {error}
            </p>
          )}

          {success && (
            <p className="rounded-md bg-green-900/30 border border-green-800 px-3 py-2 text-sm text-green-300">
              {success}
            </p>
          )}

          <button
            type="submit"
            disabled={loading}
            className="rounded-md bg-white text-black font-medium py-2 text-sm hover:bg-neutral-200 transition disabled:opacity-50"
          >
            {loading ? "Signing in…" : "Sign in"}
          </button>
        </form>

        <div className="mt-6 flex gap-4 text-sm">
          <a href="/" className="text-neutral-400 hover:text-white transition">
            ← Home
          </a>
          <a href="/vault" className="text-neutral-400 hover:text-white transition">
            Vault status →
          </a>
        </div>
      </div>
    </main>
  );
}
