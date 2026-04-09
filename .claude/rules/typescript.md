---
paths:
  - "**/*.ts"
  - "**/*.tsx"
  - "**/*.js"
  - "**/*.jsx"
---

# TypeScript — Project-Specific Rules

Claude knows TypeScript, React, Next.js. This file covers OUR deviations.

## Types

- Prefer `type` over `interface` for most things. Use `interface` only for extendable shapes.
- String literal unions over `enum`.
- No `any`. Use `unknown` and narrow.
- All shared types live in `frontend/src/types/api.ts` — one file.

## All hooks in feature directory

```text
frontend/src/features/{feature}/hooks/use-{name}.ts
```

All TanStack Query hooks live here — not scattered across components.

## Forms: Zod + react-hook-form

Schema mirrors the Pydantic backend model. `zodResolver(schema)` on every form.

## API calls unwrap envelope

```typescript
const res = await fetch('/api/v1/...')
const data = await res.json()
if (!data.ok) throw new Error(data.error?.message)
return data
```

Always check `data.ok`. Never trust raw response.

## E2E Tests — Robot Framework + Playwright

**Never use `@playwright/test` or `.spec.ts` files.** All E2E tests are Robot Framework `.robot` files using the Browser library.

```
02_frontend/tests/e2e/{feature}/
  └── 01_{sub}.robot
```

Patterns:
- API seeding in `Suite Setup` — avoid flaky UI creation flows.
- Timestamp-suffix keys for test data: `pw-${EPOCHTIME}`.
- `Wait For Load State    networkidle` before assertions.
- `data-testid` on all interactive elements — use `Get Element    [data-testid="..."]`.

**Playwright MCP** = headed live browser for manual inspection with `npm run dev` running. Not a test runner. Use when Sri asks to "test with Playwright MCP".

## No console.log

Use a proper logger. Hooks auto-detect violations.
