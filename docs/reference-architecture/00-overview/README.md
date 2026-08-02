# Overview

## Purpose

AI Enterprise is an operating system for governed software engineering. It accepts an imperfect idea
or manifesto, turns it into an auditable project, coordinates specialized agent crews, verifies work
through approvals and evidence, and promotes reusable blueprints for future delivery.

## Responsibilities

This chapter owns the system map, navigation model, and shared language used by all other chapters.
It explains how business intent moves through requirements, architecture, planning, execution,
review, integration, operations, learning, and reuse.

## Scope

The overview covers the whole platform at a high level: operator surfaces, lifecycle phases,
enterprise kernel, agent runtime, workflow runtime, telemetry, recovery, and evolution.

## Viewpoints

Business value comes from making delivery visible, controlled, reusable, and measurable. The logical
system is organized into bounded contexts. Runtime behavior is provided by FastAPI, PostgreSQL,
workers, dashboards, metrics, and graph views. Operations depend on health, readiness, jobs, audit,
and calibration signals. Evolution happens through ADRs, standards, modules, and promoted
blueprints.

## Workflow

The normal route is idea or manifesto -> project -> requirements -> approval -> architecture ->
approval -> work packages -> approval -> execution -> review -> integration -> evidence ->
blueprint candidate.

## References

- [Architecture Views](../../architecture/views.md)
- [Project Execution Walkthrough](../../enterprise/project-execution-walkthrough.md)
- [Chapter Contract](../chapter-contract.md)
