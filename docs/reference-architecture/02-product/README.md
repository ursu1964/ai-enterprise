# Product Architecture

## Purpose

The product architecture turns platform capability into a usable management experience. It must let
an operator understand the enterprise quickly, launch projects from a manifesto, inspect project
graphs, follow problems, read telemetry, and explain the product story to clients.

## Responsibilities

This chapter owns the dashboard manager, project factory, demo story, graph navigation, guided route,
human-language explanations, and product-facing proof surfaces.

## Scope

The current product surface is API-hosted: `/dashboard`, `/dashboard/demo`, `/dashboard/graphify`,
Swagger, health, readiness, metrics, and project/operator APIs.

## Interfaces

Important interfaces include project creation, project intelligence, workflow history, operator job
queues, worker instances, execution events, audit timeline, performance metrics, and graph endpoints.

## Workflow

The product guides the operator from idea clarification to manifesto launch, from project list to
project execution graph, from risk signal to recommended action, and from evidence to demo story.

## Testing

Dashboard tests must verify that business language, guided route, demo story, graph controls, and
source freshness are present without exposing raw errors as the primary user experience.

## References

- [Operator Startup Guide](../../enterprise/operator-startup-guide.md)
- [Architecture Views](../../architecture/views.md)
