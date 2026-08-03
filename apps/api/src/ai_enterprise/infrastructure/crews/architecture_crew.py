# ruff: noqa: E501 -- scripted architecture evidence keeps readable generated content.

from __future__ import annotations

from dataclasses import dataclass

from crewai import LLM, Agent, Crew, Process, Task

from ai_enterprise.config import Settings


@dataclass(frozen=True)
class ArchitectureCrewResult:
    markdown: str
    raw_output: str


class ArchitectureCrewRunner:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def run(
        self,
        *,
        project_name: str,
        project_description: str,
        project_manifest_hash: str,
        requirements_markdown: str,
        requirements_artifact_hash: str,
        revision_feedback: str | None = None,
    ) -> ArchitectureCrewResult:
        if self._settings.architecture_provider.strip().lower() == "scripted":
            requirement_ids = [
                line.split(":", 1)[0].removeprefix("- ").strip()
                for line in requirements_markdown.splitlines()
                if line.startswith("- FR-") and ":" in line
            ]
            traceability = (
                "\n".join(
                    f"- {requirement_id} -> domain services, APIs, persistence, security, observability, and acceptance tests."
                    for requirement_id in requirement_ids
                )
                or "- FR-001 -> governed workflow evidence and approval gates."
            )
            revision_section = (
                "## Revision response\n"
                f"This version incorporates the recorded review feedback:\n{revision_feedback}\n\n"
                if revision_feedback
                else ""
            )
            markdown = (
                f"# Architecture - {project_name}\n\n"
                f"Manifest: `{project_manifest_hash}`\n"
                f"Requirements artifact: `{requirements_artifact_hash}`\n\n"
                "## Architecture objectives\n"
                f"{project_description}\n\n"
                f"{revision_section}"
                "## System context and clients\n"
                "Romanian and English responsive web, mobile clients, restaurant administration, "
                "kitchen displays, courier tools, and support consoles use versioned APIs behind an "
                "edge gateway. The delivery platform remains inside the governed AI Enterprise loop.\n\n"
                "## Components and responsibilities\n"
                "- Identity and consent: social/email login, guest and family accounts, RBAC, MFA, GDPR preferences.\n"
                "- Catalog and pricing: bilingual menus, variants, allergens, nutrition, promotions, images, availability.\n"
                "- Commerce and payments: cart, scheduling, delivery fees, Stripe, Netopia, wallets, cash, invoices.\n"
                "- Order orchestration: idempotent order state machine, notifications, refunds, and live tracking.\n"
                "- Kitchen and fulfillment: KDS tickets, station routing, timers, pickup, drivers, ETA and zones.\n"
                "- Integration adapters: Glovo, Tazz, Bolt Food, SMS/email, Romanian accounting and VAT exports.\n"
                "- Inventory and procurement: recipes, stock ledger, suppliers, receiving, expiry, waste, cost and margin.\n"
                "- CRM and loyalty: segments, points, rewards, referrals, campaigns, reviews, tickets and offers.\n"
                "- AI assistance: bilingual recommendations and support with allergy disclaimers and human escalation.\n"
                "- Analytics: event-fed sales, profitability, forecasting, productivity, CLV, ROI and BI projections.\n\n"
                "## Data, APIs, and event flows\n"
                "PostgreSQL owns transactional aggregates with tenant-aware schemas; Redis supports caching, sessions, "
                "rate limits and short-lived coordination; object storage holds optimized media and immutable invoices. "
                "REST APIs expose identity, catalog, cart, checkout, orders, kitchen, delivery, inventory, CRM and reports. "
                "An outbox publishes OrderPlaced, PaymentAuthorized, StockConsumed, KitchenTicketRouted, OrderReady, "
                "CourierAssigned and OrderDelivered events. Consumers are idempotent and dead-letter failures.\n\n"
                "## Trust boundaries\n"
                "- Payment card data stays with PCI-compliant providers; only tokens and audited outcomes enter the platform.\n"
                "- External delivery, identity, messaging and accounting adapters use isolated credentials, timeouts and circuit breakers.\n"
                "- Allergy and dietary guidance is informational, shows source data, and escalates uncertain cases to staff.\n"
                "- Admin, kitchen, courier and customer roles are least-privilege; sensitive actions require MFA and audit events.\n"
                "- Human approval gates and immutable artifact hashes govern delivery changes.\n\n"
                "## Security, privacy, accessibility, and reliability\n"
                "TLS, encryption at rest, managed secrets, OWASP controls, CSP, CSRF protection, validation, rate limiting, "
                "fraud signals, audit logs, backups and restore drills protect the system. GDPR workflows support consent, "
                "export, deletion and retention. Interfaces target WCAG 2.2 AA. CDN delivery, responsive images, horizontal "
                "scaling, health probes, metrics, traces, logs and alerts support availability and performance targets.\n\n"
                "## Deployment topology and recovery\n"
                "Containerized stateless API and worker services run across multiple availability zones behind a load balancer. "
                "Managed PostgreSQL uses point-in-time recovery; queues retry with exponential backoff and dead-letter routing. "
                "Deployments use migrations, health-gated rolling releases and rollback. Provider outages degrade gracefully: "
                "orders retain state, duplicate payment and order requests are rejected by idempotency keys, and operators receive alerts.\n\n"
                "## Requirement traceability matrix\n"
                f"{traceability}\n\n"
                "## Risks and unresolved questions\n"
                "- Confirm provider contracts, production credentials, delivery webhooks, VAT rules and accounting export format.\n"
                "- Validate capacity and recovery objectives with measured load and restore tests before production launch.\n"
            )
            return ArchitectureCrewResult(markdown=markdown, raw_output=markdown)
        llm = LLM(
            model=self._settings.ollama_model,
            base_url=self._settings.ollama_base_url,
            temperature=0.1,
            timeout=900,
        )

        architect = Agent(
            role="Principal Software Architect",
            goal=(
                "Transform approved requirements into a bounded, secure, "
                "modular and auditable software architecture."
            ),
            backstory=(
                "You design enterprise platforms with explicit trust "
                "boundaries, reproducible execution, human approval gates, "
                "immutable artifacts and controlled infrastructure access."
            ),
            llm=llm,
            allow_delegation=False,
            verbose=True,
        )

        reviewer = Agent(
            role="Independent Architecture Reviewer",
            goal=(
                "Identify omissions, unsafe assumptions, uncontrolled host "
                "access, weak boundaries and requirements that are not "
                "covered by the proposed architecture."
            ),
            backstory=(
                "You perform adversarial architecture reviews for secure "
                "software delivery platforms."
            ),
            llm=llm,
            allow_delegation=False,
            verbose=True,
        )

        design_task = Task(
            description=(
                "Create an architecture specification for this project.\n\n"
                "Project: {project_name}\n"
                "Description: {project_description}\n"
                "Manifest hash: {project_manifest_hash}\n"
                "Approved requirements hash: {requirements_artifact_hash}\n\n"
                "Approved requirements:\n"
                "{requirements_markdown}\n\n"
                "Recorded revision feedback:\n"
                "{revision_feedback}\n\n"
                "The architecture must contain:\n"
                "1. Architecture objectives\n"
                "2. Scope and non-scope\n"
                "3. System context\n"
                "4. Trust boundaries\n"
                "5. Components and responsibilities\n"
                "6. Dependency direction\n"
                "7. Domain aggregates\n"
                "8. Commands and domain events\n"
                "9. Persistent data model\n"
                "10. API boundaries\n"
                "11. Worker and job execution model\n"
                "12. Agent and crew execution model\n"
                "13. Artifact and provenance model\n"
                "14. Approval gates\n"
                "15. Disposable execution environment\n"
                "16. Host protection controls\n"
                "17. Failure recovery and idempotency\n"
                "18. Observability and audit trail\n"
                "19. Security model\n"
                "20. Deployment topology\n"
                "21. Architecture decisions\n"
                "22. Requirement traceability matrix\n"
                "23. Risks and unresolved questions\n\n"
                "Every major design decision must reference the requirement "
                "IDs it satisfies. Do not silently invent requirements."
            ),
            expected_output=(
                "A complete Markdown architecture specification with "
                "component boundaries, trust boundaries, data flows, "
                "architecture decisions and requirements traceability."
            ),
            agent=architect,
        )

        review_task = Task(
            description=(
                "Review the proposed architecture independently.\n\n"
                "Verify:\n"
                "- coverage of approved requirements;\n"
                "- protection of the Ubuntu host;\n"
                "- strict human approval gates;\n"
                "- immutable artifact provenance;\n"
                "- retry and idempotency behavior;\n"
                "- database transaction boundaries;\n"
                "- container isolation;\n"
                "- absence of uncontrolled code execution.\n\n"
                "Return a corrected final architecture document. Include a "
                "review findings section describing material changes made."
            ),
            expected_output=(
                "A reviewed and corrected Markdown architecture document "
                "suitable for human approval."
            ),
            agent=reviewer,
            context=[design_task],
        )

        crew = Crew(
            agents=[architect, reviewer],
            tasks=[design_task, review_task],
            process=Process.sequential,
            verbose=True,
        )

        output = crew.kickoff(
            inputs={
                "project_name": project_name,
                "project_description": project_description,
                "project_manifest_hash": project_manifest_hash,
                "requirements_markdown": requirements_markdown,
                "requirements_artifact_hash": requirements_artifact_hash,
                "revision_feedback": revision_feedback or "No prior review feedback.",
            }
        )

        markdown = str(output).strip()

        if not markdown:
            raise RuntimeError("Architecture Crew returned an empty result")

        return ArchitectureCrewResult(
            markdown=markdown,
            raw_output=str(output),
        )
