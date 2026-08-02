# Reference Chapter Contract

Every reference architecture chapter must use this structure.

## Purpose

State why the subject exists and which enterprise problem it solves.

## Responsibilities

List what the subject owns and what it must keep reliable.

## Scope

Define the included behavior, data, interfaces, and operating boundaries.

## Non-Scope

Name responsibilities intentionally left to other chapters.

## Viewpoints

- Business viewpoint: value, measurable effect, and decision support.
- Architecture viewpoint: relationships, boundaries, dependencies, and invariants.
- Implementation viewpoint: services, modules, schemas, APIs, and workers.
- Operational viewpoint: startup, monitoring, failure handling, scale, and maintenance.
- Evolution viewpoint: extension points, versioning, migration, and future growth.

## Data Model

Describe authoritative records, identifiers, lifecycle states, and retention needs.

## Interfaces

List APIs, events, commands, dashboards, workers, and external integrations.

## Dependencies

Document upstream and downstream dependencies, including required permissions and configuration.

## Internal Components

Describe services, repositories, adapters, policies, validators, and background processors.

## Workflow

Show the normal path, approval gates, error paths, and recovery path.

## Implementation Plan

Break delivery into small slices with verification for each slice.

## Testing

Define contract, unit, integration, acceptance, and operator verification requirements.

## Security

Describe authority, isolation, secrets, audit, data exposure, and abuse prevention.

## Observability

Name metrics, logs, audit events, health checks, dashboard signals, and calibration loops.

## Future Evolution

Explain how the subject can grow without breaking current contracts.

## References

Link to standards, ADRs, API docs, runbooks, and related chapters.
