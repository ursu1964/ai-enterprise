# AI Enterprise Reference Architecture

This knowledge base is the canonical documentation product for AI Enterprise. It turns roadmap
conversation into a maintained engineering specification that can guide operators, planning crews,
implementation crews, validation crews, and future agents.

## Reading Path

Start with the enterprise book when you need operator guidance:

- [Enterprise Documentation](../enterprise/README.md)
- [Operator Startup Guide](../enterprise/operator-startup-guide.md)
- [Project Execution Walkthrough](../enterprise/project-execution-walkthrough.md)

Use this reference architecture when you need the deeper system blueprint:

- [Catalog](catalog.json) defines the complete information architecture.
- [Chapter Contract](chapter-contract.md) defines the required structure for every chapter.
- [Standards Map](standards-map.md) links each documentation area to enforceable standards.
- [ADR-0001](../adrs/0001-architecture-knowledge-base-first.md) records why this knowledge base is
  treated as the first product of the enterprise.

## Knowledge Base Shape

Every section is identified by a stable ID and one owner path. Topics should be expanded in place,
not duplicated in multiple chapters. Cross-references must point to the authoritative chapter or to
an accepted ADR.

The first implementation slice defines the complete structure before filling hundreds of pages. This
keeps the system navigable while allowing the documentation to grow module by module.

## Maintenance Rule

When code, dashboard behavior, workflow steps, manifest fields, agent contracts, standards, or
operator procedures change, update the affected reference chapter and any linked operator guide in
the same work slice.
