# Org — Planning

## Current Status
Built ✅ — Initial implementation complete and deployed.

## Backlog / Enhancement Ideas

- [ ] Add keyset-based pagination cursors for large result sets
- [ ] Expose bulk operations endpoint for high-volume admin workflows
- [ ] Emit webhook events for all state-changing operations
- [ ] Support field-level partial responses (`?fields=id,name`)

## Technical Debt

- [ ] Consolidate duplicated validation logic between service and schema layers
- [ ] Add OpenTelemetry spans to repository functions for distributed tracing
- [ ] Write integration tests covering all error branches
- [ ] Map every asyncpg exception to a typed AppError

## Future Roadmap

| Priority | Item | Target |
|----------|------|--------|
| High | E2E Playwright tests for all happy paths | Q2 2026 |
| Medium | Audit event enrichment (geo-IP, device fingerprint) | Q3 2026 |
| Medium | Per-org per-endpoint rate limiting | Q2 2026 |
| Low | GraphQL exposure via API gateway | Q4 2026 |

## Dependencies / Blockers

- None currently blocking.

## Notes

> Add design decisions, constraints, or context to consider before picking up backlog items.
