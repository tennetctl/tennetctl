---
name: tdd-workflow
description: Enforces test-driven development for all code changes. Write the failing test first, then the minimal implementation, then refactor.
origin: custom
---

# TDD Workflow

Every code change follows RED → GREEN → REFACTOR. No exceptions.

## When to Activate

- Writing new features or functionality
- Fixing bugs
- Refactoring existing code
- Adding API endpoints
- Creating new components

## The Cycle

**RED:** Write a test that describes the expected behavior. Run it. It must fail. If it passes, the test isn't testing anything new. Commit the failing test.

**GREEN:** Write the minimal code to make the test pass. Nothing more. Run all tests. The new test passes, and no existing tests break. Commit.

**REFACTOR:** Clean up the implementation without changing behavior. All tests still pass. Commit.

## Coverage

Aim for 80% or higher across unit, integration, and E2E tests combined.

- Unit tests: individual functions, utilities, pure logic
- Integration tests: API endpoints, database operations, service interactions
- E2E tests: complete user workflows through a real browser

## Rules

- Fix the implementation, not the test — unless the test itself is provably wrong.
- Commit after each stage (RED, GREEN, REFACTOR) as a checkpoint.
- Never skip RED. If you can't write a failing test first, you don't understand the requirement well enough.
- Run the full test suite after GREEN to catch regressions.
