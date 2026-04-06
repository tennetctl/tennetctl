# Ethos

These are the principles that guide every decision in tennetctl — from architecture choices to API design to what features get built and in what order.

When a decision is hard, come back here.

---

## 1. Simple enough to understand, complete enough to trust

Every module must be simple enough that a developer can read the source code and fully understand what it does in under an hour. No magic, no framework abstractions that hide behavior, no "trust us, it works."

At the same time, simple does not mean incomplete. A simplified secrets manager that leaks keys on key rotation is not simple — it is broken. Simple means the fewest moving parts that still deliver the full guarantee.

**In practice:** Prefer boring technology. Raw SQL over an ORM. A Postgres table over a separate queue service. An explicit function over a decorator-based framework.

---

## 2. One dependency at a time

Every required external dependency is a deployment burden, a failure mode, and a maintenance cost. tennetctl has exactly two required external dependencies: **Postgres** and **NATS**. Everything else is optional and additive.

Before adding a new dependency, the question is: can we do this with Postgres or NATS? If yes, use them. If not, the new dependency must be genuinely irreplaceable — not just more convenient.

Optional dependencies (ClickHouse, Redis, S3-compatible storage) are supported via pluggable backends with a Postgres default. Users who never need scale never install anything extra.

---

## 3. Postgres is the source of truth

All durable state lives in Postgres. Not in NATS, not in application memory, not in a cache that might be stale.

NATS JetStream is used for high-volume ingestion pipelines (monitoring logs, traces, metrics) where Postgres cannot absorb the write rate at the point of entry. But even then, the consumer workers write everything to Postgres. NATS is a pipe, not a database.

This means: if Postgres is healthy, the system is healthy. Operators understand and trust Postgres. They know how to back it up, inspect it, and recover it. tennetctl leverages that expertise rather than fighting it.

---

## 4. Modules are isolated, integration is explicit

tennetctl ships as one process with eight modules. This does not mean the modules are tangled together.

Each module owns its own Postgres schema. Modules never import each other's service layers. Cross-module communication happens only via the internal event bus (Postgres LISTEN/NOTIFY + transactional outbox). If you want to understand what the IAM module does, you read the IAM module. Its behavior is not distributed across six other modules.

This isolation is also what makes tennetctl composable. A team that only wants to use the Vault module can deploy tennetctl and simply not configure the other modules. The cost of unused modules is near zero.

---

## 5. Security is not a feature, it is the foundation

IAM, audit, and vault are not features added on top of tennetctl. They are the foundation that everything else is built on. Every module assumes:

- All data is accestennetctlled via Row-Level Security at the database layer
- All state changes emit an audit event
- All secrets are encrypted at rest
- All API endpoints are authenticated unless explicitly marked public

Security failures in a control plane are catastrophic. tennetctl treats security as a first-class constraint, not an afterthought.

---

## 6. Open source means genuinely open

tennetctl is open source because the problem it solves is universal and the community benefits from working on it together. Open source here means:

- The entire codebase is public and MIT licensed
- Every architectural decision is documented with its rationale
- Contributing is documented clearly enough that an external developer can add a feature without talking to the core team
- No features are paywalled or reserved for a commercial edition

If tennetctl ever becomes a commercial product, it will do so through hosting, support, and enterprise services — never by taking open-source features and hiding them behind a paywall.

---

## 7. Documentation is part of the code

A feature is not complete until it is documented. Not "we'll write the docs later" — the docs are part of the definition of done.

Every module has:
- A plain-English explanation of what it does and why
- Architecture documentation that explains the design decisions
- API documentation generated from the code
- A contributing guide specific to that module

This is not about covering our backs. It is about respecting the time of every developer who will read this code.

---

## 8. Build for the team of one, scale for the team of one hundred

The default configuration should work out of the box for a solo developer with no infrastructure expertise. Postgres on a $20 VPS, NATS in Docker, and tennetctl running next to it.

Scaling should be a configuration change, not a rewrite. The abstractions (storage backends, event bus implementations, rate limiting backends) are designed so that a team that grows can swap in ClickHouse or Redis without changing application code.

tennetctl should never require you to be an infrastructure engineer to run it. It should never require you to hire one to scale it.
