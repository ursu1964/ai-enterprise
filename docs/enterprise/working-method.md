# AI Enterprise Working Method

Every implementation slice follows the same discipline.

## 1. Plan

State the business goal, affected dashboard or API surface, expected data sources, and verification
plan before changing behavior.

## 2. Execute

Implement the smallest useful slice connected to real application data. Avoid placeholder dashboard
claims that are not backed by an endpoint, database record, event stream, or generated artifact.

## 3. Verify

Run focused tests for the changed surface. Run broader gates when shared behavior, API contracts,
dashboard routing, migrations, or data projections change.

Expected gates:

- Focused pytest suite for the changed behavior.
- Ruff for touched Python files.
- Mypy when backend contracts or projections change.
- Alembic heads when migrations are touched or database behavior is relevant.
- Live HTTP checks for dashboard, health, and affected endpoints.
- For autonomy changes, run a controlled mock factory start and inspect the Execution dashboard
  before treating the operating loop as active.
- `graphify update .` after code or documentation changes.

## 4. Document

If verification passes, update the affected documentation in the same change. Documentation must say
what changed, where the operator can see it, which endpoint or data source backs it, and which
verification was run.

## Required Close-Out

Do not call a slice complete until these questions have clear answers:

- What changed?
- Where can it be seen?
- Which data source feeds it?
- How was it verified?
- Which documentation was updated?
