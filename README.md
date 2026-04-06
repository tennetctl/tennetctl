# tennetctl

**You shouldn't need 30 tools to ship one app.**

tennetctl is a single, self-hosted control plane for running any SaaS product in production. One deployment. One database. One dashboard. Everything you need to operate a product — identity, observability, secrets, notifications, analytics, and more — as a unified system with deep integration between modules.

No more stitching together Auth0, Prometheus, Grafana, HashiCorp Vault, LaunchDarkly, Mixpanel, and PagerDuty. Run one command and have all of it, integrated, backed by one Postgres database you own and control.

---

## Modules

| # | Module | Status | Replaces |
|---|--------|--------|----------|
| 01 | Foundation | ✅ Done | — |
| 02 | IAM | ✅ Done | Auth0, Clerk, WorkOS |
| 03 | Audit | ✅ Done | — |
| 04 | Vault | 🔨 Building | HashiCorp Vault |
| 05 | Monitoring | 🔨 Building | Prometheus, Grafana, Loki, Jaeger, PagerDuty |
| 06 | Notifications | 🔨 Building | SendGrid, Mailchimp, Twilio |
| 07 | Product Ops | 🔨 Building | Mixpanel, Plausible, LaunchDarkly |
| 08 | LLM Ops | 📋 Planned | Langfuse, Helicone |

---

## Quick Start

**Requirements:** Docker + Docker Compose, Python 3.12+, Node.js 20+, [uv](https://docs.astral.sh/uv/)

```bash
git clone https://github.com/tennetctl/tennetctl.git
cd tennetctl

# Start Postgres + NATS
docker compose up -d postgres nats

# Backend
cd backend && uv sync && cp .env.example .env
uv run python -m scripts.migrate up
uv run uvicorn main:app --reload --port 51734

# Frontend (new terminal)
cd frontend && npm install && cp .env.local.example .env.local
npm run dev
```

Open [http://localhost:51735](http://localhost:51735). Full setup guide: [03_docs/00_main/06_setup.md](03_docs/00_main/06_setup.md)

---

## Infrastructure

Two required dependencies. Everything else is optional.

| Dependency | Required | Purpose |
|------------|----------|---------|
| PostgreSQL 16 | ✅ | All durable state |
| NATS 2.10 JetStream | ✅ | High-volume ingest (metrics, traces, logs) |
| Minio | Optional | Object storage (attachments, exports) |
| Valkey | Optional | Caching, rate limiting |
| ClickHouse | Optional | High-cardinality time-series at scale |

---

## Feature Gating

tennetctl ships as a single Docker image. Enable only what you need:

```bash
# Only IAM + Audit + Vault
TENNETCTL_MODULES=iam,audit,vault docker compose up

# Everything
TENNETCTL_MODULES=all docker compose up
```

---

## Documentation

| Document | Description |
|----------|-------------|
| [Vision](03_docs/00_main/01_vision.md) | Why tennetctl exists |
| [Ethos](03_docs/00_main/02_ethos.md) | Design principles |
| [Setup](03_docs/00_main/06_setup.md) | Full local development guide |
| [Roadmap](03_docs/00_main/04_roadmap.md) | What's built and what's next |
| [Contributing](CONTRIBUTING.md) | How to contribute |
| [Architecture Decisions](03_docs/00_main/08_decisions/) | Why things are the way they are |

---

## Contributing

All contributions are welcome — bug reports, fixes, features, and docs. Every change goes through a PR, including changes from the maintainer.

Read [CONTRIBUTING.md](CONTRIBUTING.md) to get started.

---

## License

[AGPL-3.0](LICENSE) — free to self-host, modify, and contribute. If you offer tennetctl as a hosted service, your modifications must be open sourced.
