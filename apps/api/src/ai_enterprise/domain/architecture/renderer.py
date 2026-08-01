from ai_enterprise.domain.architecture.schema import ArchitectureArtifactDocument


def _section(title: str, values: tuple[str, ...]) -> list[str]:
    return [f"## {title}", "", *[f"- {value}" for value in values], ""]


def render_architecture_markdown(document: ArchitectureArtifactDocument) -> str:
    lines = ["# Architecture", "", "## Overview", "", document.overview, ""]
    lines += _section("Goals", document.goals)
    lines += _section("Constraints", document.constraints)
    lines += ["## Functional decomposition", ""]
    for domain in document.functional_domains:
        lines += [f"### {domain.id}: {domain.name}", ""]
        lines += [f"- {item}" for item in domain.responsibilities] + [""]
    lines += ["## Modules", ""]
    for module in document.modules:
        lines += [f"### {module.id}: {module.name}", "", f"Domain: `{module.domain_id}`", ""]
        lines += [f"- {item}" for item in module.responsibilities] + [""]
    lines += _section("Deployment", document.deployment)
    lines += _section("Security", document.security)
    lines += _section("Reliability", document.reliability)
    lines += _section("Failure scenarios", document.failure_scenarios)
    lines += _section("Scaling", document.scaling)
    lines += _section("Observability", document.observability)
    lines += _section("Risks", document.risks)
    lines += _section("Open Questions", document.open_questions)
    lines += ["## Requirement traceability", ""]
    for trace in document.requirement_traceability:
        lines.append(
            f"- `{trace.requirement_id}`: {', '.join(f'`{x}`' for x in trace.design_element_ids)}"
        )
    return "\n".join(lines).rstrip() + "\n"
