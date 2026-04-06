# ADR-015: Feature Module Gating — Single Container, Selective Activation

**Status:** ACCEPTED  
**Date:** 2026-04-02  
**Supersedes:** None  
**Related:** ADR-001 (Postgres primary), ADR-004 (no extra deps), Ethos §4 (module isolation)

---

## Context

tennetctl ships as a single Docker image containing all 8 feature modules (IAM, Audit, Vault, Monitoring, Notifications, Product Ops, LLM Ops, and Foundation). While the "one control plane" vision is the core differentiator, real-world deployments have different needs:

| Deployment | Needs | Does NOT need |
|---|---|---|
| Solo dev on a $20 VPS | IAM, Vault, Audit | Monitoring (resource-heavy), LLM Ops |
| Mid-stage SaaS (10-person team) | IAM, Vault, Audit, Monitoring, Notifications | LLM Ops, Product Ops |
| AI-native startup | IAM, Vault, Audit, LLM Ops | Full Monitoring (uses Datadog externally) |
| Full enterprise deployment | Everything | — |

Problems without gating:
- **Resource waste**: Monitoring ingest workers, NATS consumers, and background schedulers consume CPU/memory even when unused
- **Attack surface**: Disabled modules still expose routes if not gated
- **Operational noise**: Log output, health checks, and dashboard clutter from unused modules
- **Migration burden**: Running migrations for modules you'll never use

---

## Decision

**Every feature module is independently activatable via a single environment variable.** The container ships with all modules, but only enabled modules register routes, start workers, run background tasks, and appear in the UI.

### Activation Model

```bash
# Enable specific modules (comma-separated module codes)
TENNETCTL_MODULES=iam,audit,vault,monitoring,notify

# Or enable everything (default for local dev)
TENNETCTL_MODULES=all
```

### Module Registry

| Code | Module | Always On? | Default |
|------|--------|-----------|---------|
| `core` | Foundation (01) | **Yes** — cannot be disabled | Always enabled |
| `iam` | Identity & Access (02) | **Yes** — required by all others | Always enabled |
| `audit` | Audit Trail (03) | **Yes** — security mandate | Always enabled |
| `vault` | Secrets Management (04) | No | Enabled |
| `monitoring` | Observability (05) | No | Disabled |
| `notify` | Notifications (06) | No | Disabled |
| `product_ops` | Product Analytics (07) | No | Disabled |
| `llm_ops` | LLM Observability (08) | No | Disabled |

**Core, IAM, and Audit are always on.** They are the security foundation. Disabling them would break the guarantees in Ethos §5 ("Security is not a feature, it is the foundation").

---

## Architecture

### Layer 1: Configuration (`01_core/config.py`)

```python
class ModuleConfig(BaseSettings):
    """Feature module activation flags.

    Controls which modules register routes, start workers,
    and appear in the frontend navigation.
    """
    TENNETCTL_MODULES: str = Field(
        default="iam,audit,vault",
        description="Comma-separated module codes or 'all'"
    )

    @property
    def enabled_modules(self) -> set[str]:
        """Return the set of enabled module codes."""
        raw = self.TENNETCTL_MODULES.strip()
        if raw == "all":
            return {"core", "iam", "audit", "vault", "monitoring", "notify", "product_ops", "llm_ops"}
        codes = {c.strip() for c in raw.split(",")}
        # Force mandatory modules
        codes |= {"core", "iam", "audit"}
        return codes

    def is_enabled(self, module_code: str) -> bool:
        """Check if a specific module is enabled."""
        return module_code in self.enabled_modules
```

### Layer 2: Backend — Conditional Route Registration (`main.py`)

```python
from importlib import import_module

# Always registered (mandatory)
app.include_router(_iam_routes.router, prefix="/api/v1")
app.include_router(_audit_routes.router, prefix="/api/v1")

# Conditionally registered
if config.is_enabled("vault"):
    _vault = import_module("backend.02_features.vault")
    app.include_router(_vault.router, prefix="/api/v1")

if config.is_enabled("monitoring"):
    _monitoring = import_module("backend.02_features.monitoring")
    app.include_router(_monitoring.router, prefix="/api/v1")
    # Start NATS consumers, background schedulers, etc.
    _monitoring.start_workers(app)

# ... repeat for each optional module
```

**Disabled modules:**
- Do NOT register any FastAPI routes → requests return 404, not 403
- Do NOT start NATS consumers or background tasks → zero CPU cost
- Do NOT appear in `/api/v1/system/modules` enabled list

### Layer 3: Backend — Module Status Endpoint

```
GET /api/v1/system/modules
```

Returns:
```json
{
  "ok": true,
  "data": [
    {"code": "core",       "name": "Foundation",        "status": "always_on"},
    {"code": "iam",        "name": "Identity & Access",  "status": "always_on"},
    {"code": "audit",      "name": "Audit Trail",        "status": "always_on"},
    {"code": "vault",      "name": "Secrets Management", "status": "enabled"},
    {"code": "monitoring", "name": "Observability",      "status": "disabled"},
    {"code": "notify",     "name": "Notifications",      "status": "disabled"},
    {"code": "product_ops","name": "Product Analytics",   "status": "disabled"},
    {"code": "llm_ops",    "name": "LLM Observability",  "status": "disabled"}
  ]
}
```

### Layer 4: Frontend — Dynamic Navigation

The frontend fetches `/api/v1/system/modules` on app load and stores it in a React context:

```typescript
// src/features/system/hooks/use-modules.ts
export function useModules() {
  return useQuery({
    queryKey: ['system-modules'],
    queryFn: async () => {
      const res = await fetch('/api/v1/system/modules')
      const data = await res.json()
      return data.data
    },
    staleTime: 300_000, // 5 min — modules don't change at runtime
  })
}

export function useModuleEnabled(code: string): boolean {
  const { data } = useModules()
  return data?.some(m => m.code === code && m.status !== 'disabled') ?? false
}
```

Sidebar navigation conditionally renders links:

```tsx
{isEnabled('vault') && <NavLink href="/vault">Secrets</NavLink>}
{isEnabled('monitoring') && <NavLink href="/monitoring">Observability</NavLink>}
```

**Disabled module pages** show a "Module Not Enabled" placeholder if accessed directly via URL, not a 404. This lets users discover features they can enable.

### Layer 5: Database — Migrations Always Run

**All migrations run regardless of enabled modules.** Schema creation is cheap and idempotent. This ensures:
- Enabling a module later doesn't require a migration catch-up
- Cross-module event consumers can reference target schemas even if the producing module is disabled
- Backup/restore works cleanly — no conditional schema gaps

---

## Resource Impact

| Module | Disabled CPU | Disabled Memory | Main Cost When Enabled |
|--------|-------------|----------------|----------------------|
| Vault | 0 | 0 | Encryption operations |
| Monitoring | 0 (no NATS consumers, no alert evaluator) | ~0 | NATS consumers, alert eval worker (every 10s), log indexing |
| Notifications | 0 (no delivery queue worker) | ~0 | SMTP connections, delivery queue polling |
| Product Ops | 0 (no event ingest consumer) | ~0 | NATS event consumer, aggregation workers |
| LLM Ops | 0 (no trace consumer) | ~0 | LLM trace ingest, cost aggregation |

**Key insight:** The heavy-resource modules (Monitoring, Product Ops, LLM Ops) are all driven by NATS consumers and background workers. When disabled, those goroutines/tasks simply never start. The cost is genuinely zero, not "low."

---

## Deployment Profiles (Convenience)

For common deployment patterns, provide named profiles as shorthand:

```bash
# Minimal — solo dev, just auth and secrets
TENNETCTL_PROFILE=minimal
# Equivalent to: TENNETCTL_MODULES=iam,audit,vault

# Standard — most SaaS teams
TENNETCTL_PROFILE=standard
# Equivalent to: TENNETCTL_MODULES=iam,audit,vault,monitoring,notify

# Full — everything
TENNETCTL_PROFILE=full
# Equivalent to: TENNETCTL_MODULES=all

# Custom — explicit module list (overrides profile)
TENNETCTL_MODULES=iam,audit,vault,llm_ops
```

`TENNETCTL_MODULES` takes precedence over `TENNETCTL_PROFILE` if both are set.

---

## What This Does NOT Do

- **Runtime toggling**: Modules are enabled at container start. Changing the module list requires a restart. This is deliberate — feature gating at runtime introduces state management complexity that doesn't justify the benefit for infrastructure software.
- **Per-org module gating**: All enabled modules are available to all orgs. Per-org feature visibility is a future concern (tracked separately, potentially via existing feature flags).
- **Partial module activation**: A module is fully on or fully off. You cannot enable "monitoring metrics" but disable "monitoring traces." Sub-feature gating within a module is a separate concern handled by the module's own config.

---

## Alternatives Considered

### 1. Separate containers per module
**Rejected.** This becomes a microservices architecture. Breaks the "one deployment" vision. Introduces inter-service networking, service discovery, and deployment orchestration complexity. The whole point of tennetctl is avoiding this.

### 2. Plugin architecture with dynamic loading
**Rejected.** Over-engineered for 8 modules. Adds complexity (plugin discovery, version compatibility, dependency resolution) without proportional benefit. tennetctl ships all modules — the question is only which ones activate.

### 3. Compile-time feature flags (build separate images per profile)
**Rejected.** Multiplies the number of Docker images. Complicates CI/CD. Users want one image that works everywhere.

### 4. Always-on, just hide UI
**Rejected.** Routes still accept traffic (security risk). Background workers still consume resources. Logs still produce noise. Hiding the sidebar link is cosmetic, not functional.

---

## Implementation Checklist

- [ ] Add `TENNETCTL_MODULES` and `TENNETCTL_PROFILE` to `01_core/config.py`
- [ ] Add `is_enabled()` gate function to `01_core/config.py`
- [ ] Refactor `main.py` to conditionally register routers based on enabled modules
- [ ] Add `GET /api/v1/system/modules` endpoint to `01_core`
- [ ] Add `useModules()` and `useModuleEnabled()` hooks to frontend
- [ ] Update sidebar navigation to conditionally render module links
- [ ] Add "Module Not Enabled" placeholder page component
- [ ] Update `docker-compose.yml` to document `TENNETCTL_MODULES` env var
- [ ] Update `06_setup.md` with module activation documentation
- [ ] Add integration tests for enabled/disabled module routing behavior
