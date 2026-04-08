export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-8 p-12">
      <div className="text-center">
        <h1 className="text-4xl font-bold tracking-tight">tennetctl</h1>
        <p className="mt-2 text-neutral-400">S-Control platform</p>
      </div>

      <nav className="flex flex-col gap-3 w-full max-w-xs">
        <a
          href="/iam"
          className="flex items-center justify-between rounded-md border border-white/10 bg-white/5 px-4 py-3 text-sm hover:bg-white/10 transition"
        >
          <span>IAM — Sign in</span>
          <span className="text-neutral-500">→</span>
        </a>
        <a
          href="/vault"
          className="flex items-center justify-between rounded-md border border-white/10 bg-white/5 px-4 py-3 text-sm hover:bg-white/10 transition"
        >
          <span>Vault — Status</span>
          <span className="text-neutral-500">→</span>
        </a>
        <a
          href="http://localhost:8000/healthz"
          className="flex items-center justify-between rounded-md border border-white/10 bg-white/5 px-4 py-3 text-sm hover:bg-white/10 transition"
        >
          <span>Backend — healthz</span>
          <span className="text-neutral-500">→</span>
        </a>
      </nav>
    </main>
  );
}
