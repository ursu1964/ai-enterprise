from __future__ import annotations

from dataclasses import dataclass

from ai_enterprise.domain.architecture.schema import ArchitectureArtifactDocument


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    code: str
    location: str
    message: str


class ArchitectureValidationError(ValueError):
    def __init__(self, issues: tuple[ValidationIssue, ...]) -> None:
        self.issues = issues
        super().__init__("; ".join(f"{item.code}: {item.message}" for item in issues))


def validate_architecture(
    document: ArchitectureArtifactDocument, *, approved_requirement_ids: frozenset[str]
) -> None:
    issues: list[ValidationIssue] = []
    domains = {item.id for item in document.functional_domains}
    modules = {item.id for item in document.modules}
    elements = (
        domains
        | modules
        | {item.id for item in document.interfaces}
        | {item.id for item in document.data_entities}
    )
    for module in document.modules:
        if module.domain_id not in domains:
            issues.append(ValidationIssue("orphan_module", module.id, module.domain_id))
        for dependency in module.dependencies:
            if dependency not in modules:
                issues.append(ValidationIssue("unknown_dependency", module.id, dependency))
    graph = {item.id: item.dependencies for item in document.modules}
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> None:
        if node in visiting:
            issues.append(ValidationIssue("circular_dependency", node, "module dependency cycle"))
            return
        if node in visited:
            return
        visiting.add(node)
        for child in graph.get(node, ()):
            if child in graph:
                visit(child)
        visiting.remove(node)
        visited.add(node)

    for module_id in graph:
        visit(module_id)
    for contract in document.interfaces:
        if contract.owner_module_id not in modules:
            issues.append(
                ValidationIssue("unknown_interface_owner", contract.id, contract.owner_module_id)
            )
    for entity in document.data_entities:
        if entity.owner_module_id not in modules:
            issues.append(
                ValidationIssue("unknown_entity_owner", entity.id, entity.owner_module_id)
            )
    traced: set[str] = set()
    for trace in document.requirement_traceability:
        if trace.requirement_id not in approved_requirement_ids:
            issues.append(
                ValidationIssue("invented_requirement", trace.requirement_id, "not approved")
            )
        traced.add(trace.requirement_id)
        for element in trace.design_element_ids:
            if element not in elements:
                issues.append(
                    ValidationIssue("unknown_design_element", trace.requirement_id, element)
                )
    for missing in sorted(approved_requirement_ids - traced):
        issues.append(
            ValidationIssue("missing_requirement_trace", missing, "requirement is uncovered")
        )
    if issues:
        raise ArchitectureValidationError(tuple(issues))
