---
name: e2e-testing
description: Write E2E tests for web app user flows. Use when creating or updating end-to-end tests.
origin: custom
---

# E2E Testing

E2E tests verify complete user flows through a real browser. The goal is confidence that the system works end-to-end, not implementation coverage.

## When to Activate

- Writing new E2E tests for a feature
- Updating existing tests after UI changes
- Debugging flaky E2E tests

## Test Stack

Prefer Robot Framework with the Playwright Browser library for structured, readable test suites. Follow the project's existing test framework if already established — don't mix frameworks.

## Test Location

Follow the project's convention. Typical pattern: `tests/e2e/{feature}/` or `tests/e2e/{feature}_{sub}.robot`.

## Conventions

- **Seed data via API, not UI.** Set up test data in Suite Setup through API calls. UI-driven setup is slow and flaky.
- **Unique test data.** Use timestamp or UUID suffixes on keys to avoid collisions between runs.
- **Wait for network.** Wait for `networkidle` (or equivalent) load state before asserting — don't sleep.
- **Testids.** Add `data-testid` attributes to all interactive elements in the frontend. Locate by testid, not by CSS classes or text that can change.
- **Auto-wait locators.** Use locator-based APIs that auto-wait, not imperative waits.

## Flaky Test Handling

Run locally 3-5 times before committing. Common causes:
- Race conditions → use auto-wait locators
- Network timing → wait for specific responses
- Animations → wait for networkidle

Quarantine genuinely flaky tests with a comment and a tracking reference. Don't delete — understand first.

## Playwright MCP

Playwright MCP is for live browser inspection alongside a dev server — not a test runner. Use it for debugging and visual checks. Always headed, never headless.
