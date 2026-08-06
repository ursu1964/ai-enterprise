# AI Enterprise Universal Experience Runtime

This is the client-facing web surface for the R1 blueprint flow and the R10 Universal
Experience & Interaction Framework in `1/r10.txt`.

It is intentionally static: no build pipeline, no framework dependency, and no separate deployment
service. The FastAPI application serves it at `/client-portal`.

The portal drives the implemented project path:

1. Load or paste an AEPM v0.1 manifest.
2. Import it through `/api/v1/project-formation/client-blueprints/import`.
3. Review, approve, or submit corrections to the canonical project blueprint.
4. Download the traceable project blueprint.
5. Bootstrap R10 role workspaces against the imported project.
6. Subscribe to `/api/v1/projects/{project_id}/ueif/events` and poll
   `/api/v1/projects/{project_id}/ueif/*` as a fallback for dashboard and record changes.
7. Record role-aware collaboration threads and AI proposals as governed UEIF records.

The runtime uses `EventSource` for server-sent R10 snapshots and `BroadcastChannel` when available
so multiple open clients for the same project refresh when one client writes collaboration or
proposal records.
