# AI Enterprise Knowledge Base

This is the main documentation index for AI Enterprise. It connects operator guides, enterprise
architecture, engineering standards, ADRs, and runbooks into one maintained knowledge base.

## Start Here

- [Enterprise Documentation](enterprise/README.md): operator-facing map, dashboard routes, startup,
  project factory, telemetry, and lifecycle walkthroughs.
- [Architecture Views](architecture/README.md): business, logical, runtime, deployment,
  operational, and evolution views of the platform.
- [Reference Architecture](reference-architecture/README.md): canonical chapter catalog and chapter
  contract for long-term architecture documentation.

## Governance

- [ETRA Standards](etra/README.md): enforceable engineering standards.
- [Architecture Decision Records](adrs/README.md): accepted architecture decisions.
- [Runbooks](runbooks/service-operations.md): operating, recovery, evolution, federation, and agent
  runtime procedures.

## Operator Guides

- [Operator Startup Guide](enterprise/operator-startup-guide.md)
- [Project Execution Walkthrough](enterprise/project-execution-walkthrough.md)
- [AI Enterprise Working Method](enterprise/working-method.md)
- [Documentation Command Center](enterprise/documentation-command-center.md)
- [Local Bootstrap](local-bootstrap.md)

## Maintenance

Every implementation slice follows plan, execute, verify, then document. Operator behavior goes in
`docs/enterprise`, deep architecture goes in `docs/architecture` or `docs/reference-architecture`,
standards go in `docs/etra`, and durable decisions go in `docs/adrs`.
