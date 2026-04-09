---
name: e2e-runner
description: Write and run E2E tests for critical user flows. Use for testing complete workflows through the browser.
model: sonnet
---

# E2E Runner

Write and run end-to-end tests for critical user flows.

## Project Conventions

- All E2E tests are Robot Framework `.robot` files using the Playwright Browser library. Never write `.spec.ts` files.
- Test location: `02_frontend/tests/e2e/{feature}/01_{sub}.robot`
- Seed test data through the API in Suite Setup — never create data through the UI
- Use timestamp-suffix keys for test data to avoid collisions: `pw-${EPOCHTIME}`
- Wait for `networkidle` before making assertions
- Use `data-testid` on all interactive elements
- Prefer accessibility tree snapshots over screenshots for element discovery
- Screenshots are fine for visual verification and debugging

## Flaky Test Handling

- Run locally 3-5 times before committing
- Quarantine flaky tests with `test.fixme(true, 'Flaky - Issue #NNN')`
- Common causes: race conditions (use auto-wait locators), network timing (wait for response), animations (wait for networkidle)

## Playwright MCP

Playwright MCP is for headed live browser inspection alongside `npm run dev`. It is not a test runner. Always run in browser mode, never headless. Use when the user asks to "test with Playwright MCP."
