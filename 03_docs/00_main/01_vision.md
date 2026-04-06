# Vision

## The Problem

Running a production SaaS today requires stitching together 20-30 separate tools before your first user signs in.

You need Zitadel or Clerk for authentication. Prometheus and Grafana for metrics. Loki for logs. Jaeger for traces. HashiCorp Vault for secrets. Mailchimp for email. SendGrid for transactional notifications. Mixpanel for product analytics. Plausible for web analytics. LaunchDarkly for feature flags. PagerDuty for on-call. Langfuse for LLM observability. Each tool has its own:

- Deployment and maintenance burden
- Pricing model and vendor lock-in
- Authentication system
- Data model that doesn't talk to the others
- Dashboard you have to learn
- API you have to integrate

This is madness. A solo developer or small team shouldn't need a dedicated DevOps engineer just to get a product to a production-grade baseline.

## What tennetctl Is

tennetctl is a single, self-contained control plane for running any SaaS product in production.

One deployment. One database. One dashboard. Everything you need to operate a product — identity, observability, secrets, notifications, analytics, and more — shipped as a unified system with deep integration between modules.

It is not a collection of loosely coupled microservices. It is one application with one Postgres database, designed to run on a single server and scale horizontally when needed.

## Who It Is For

tennetctl is built for:

- **Solo developers and small teams** who want production-grade infrastructure without the operational complexity of running 20 separate tools
- **Mid-scale SaaS products** (up to millions of events/day) that need serious observability, proper IAM, and reliable notifications without enterprise pricing
- **Developers who value ownership** over their data and infrastructure — no SaaS lock-in, self-hosted by default
- **Open-source contributors** who want to build something that matters to real builders

tennetctl is not built for:

- Hyperscale systems with billions of events per day (those systems need dedicated infrastructure for each concern)
- Organizations that require compliance certifications for their tooling vendors (use enterprise-grade vendors for that)
- Teams that prefer managed SaaS over self-hosting (great options exist for you)

## The Goal

A developer starting a new product should be able to run one command:

```bash
docker compose up
```

And have running, production-ready:

- User authentication with MFA, SSO, and OAuth
- Full observability: metrics, traces, logs, and alerts
- Secrets management with rotation
- Transactional and marketing notifications
- Product analytics and feature flags
- LLM observability if they're building AI features

All of it integrated, all of it queryable from one dashboard, all of it backed by one Postgres database they own and control.

## What tennetctl Will Never Become

- A cloud service with a free tier and paywalled features
- A platform that phones home or collects telemetry without consent
- A system with required external dependencies beyond Postgres and NATS
- An enterprise product that ignores the needs of small teams
- A monorepo of loosely related tools marketed as a platform

tennetctl is infrastructure for builders. It stays that way.
