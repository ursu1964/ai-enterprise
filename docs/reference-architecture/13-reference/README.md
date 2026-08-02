# Reference Catalogs

## Purpose

Reference catalogs make reusable knowledge discoverable. They keep schemas, templates, agents,
crews, workflows, modules, and blueprints in one governed information architecture.

## Responsibilities

This chapter owns schema catalogs, template catalogs, agent catalogs, crew catalogs, workflow
catalogs, module catalogs, blueprint references, and cross-reference rules.

## Data Model

Catalog entries need stable IDs, titles, owner paths, status, owned concepts, references, and
evidence links when promoted from real project work.

## Workflow

A reusable item starts as project evidence, becomes a candidate, receives review, gains an owner
path, links to standards or ADRs, and is promoted only when its value is proven.

## Testing

Catalog tests should verify required files, valid JSON catalogs, link integrity, non-empty content,
and absence of placeholder markers.

## Evolution

Catalogs should grow into a blueprint marketplace where future projects can select proven patterns,
project templates, crew templates, and compliance packs.

## References

- [Reference Architecture Catalog](../catalog.json)
- [Documentation Standard](../../etra/documentation-standard.md)
