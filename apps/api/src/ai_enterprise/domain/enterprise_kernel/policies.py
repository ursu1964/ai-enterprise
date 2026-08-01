from .entities import (
    EnterpriseModule,
    EnterpriseResource,
    EnterpriseSchedule,
    OperatingMaturitySnapshot,
    OrganizationalThread,
)
from .enums import EnterpriseResourceType
from .exceptions import (
    InvalidEnterpriseModule,
    InvalidEnterpriseResource,
    InvalidEnterpriseSchedule,
    InvalidOperatingMaturity,
    InvalidOrganizationalThread,
)


class ResourceRegistrationPolicy:
    """P11 kernel invariant: no enterprise object may enter unmanaged."""

    def require_managed(self, resource: EnterpriseResource) -> None:
        if resource.version != 1:
            raise InvalidEnterpriseResource("Initial enterprise resource version must be 1")
        if not resource.owner_id.strip():
            raise InvalidEnterpriseResource("Enterprise resources require an accountable owner")
        if not resource.access_policy_ids:
            raise InvalidEnterpriseResource("Enterprise resources require access policy bindings")
        if not resource.governance_policy_ids:
            raise InvalidEnterpriseResource(
                "Enterprise resources require governance policy bindings"
            )
        if not resource.retention_policy_id.strip():
            raise InvalidEnterpriseResource("Enterprise resources require a retention policy")
        if not resource.provenance:
            raise InvalidEnterpriseResource("Enterprise resources require provenance")
        if not resource.evidence:
            raise InvalidEnterpriseResource("Enterprise resources require audit evidence")


class EnterpriseSchedulingPolicy:
    """P11 kernel invariant: scheduled organizational work is explicit and bounded."""

    def require_schedulable(self, schedule: EnterpriseSchedule) -> None:
        if schedule.priority < 0 or schedule.priority > 100:
            raise InvalidEnterpriseSchedule("Schedule priority must be between 0 and 100")
        if schedule.target_resource_version < 1:
            raise InvalidEnterpriseSchedule("Schedule target resource version must be positive")
        if len(schedule.dependencies) != len(set(schedule.dependencies)):
            raise InvalidEnterpriseSchedule("Schedule dependencies must be unique")
        if schedule.target_resource_id in schedule.dependencies:
            raise InvalidEnterpriseSchedule("Schedule cannot depend on its target resource")
        if not schedule.required_approval_gate_ids:
            raise InvalidEnterpriseSchedule("Schedule requires explicit approval gates")
        if not schedule.capability_requirements:
            raise InvalidEnterpriseSchedule("Schedule requires capability requirements")
        if not schedule.resource_claims:
            raise InvalidEnterpriseSchedule("Schedule requires bounded resource claims")
        if any(claim.amount <= 0 for claim in schedule.resource_claims):
            raise InvalidEnterpriseSchedule("Schedule resource claims must be positive")
        if not schedule.evidence:
            raise InvalidEnterpriseSchedule("Schedule requires supporting evidence")


class EnterpriseModulePolicy:
    """P11 invariant: replaceable modules enter through governed registration."""

    def require_governed_module(self, module: EnterpriseModule) -> None:
        if not module.capability_ids:
            raise InvalidEnterpriseModule("Enterprise modules require capability bindings")
        if not module.owned_resource_ids:
            raise InvalidEnterpriseModule("Enterprise modules require managed owned resources")
        if not module.governance_policy_ids:
            raise InvalidEnterpriseModule("Enterprise modules require governance policies")
        if not module.evidence:
            raise InvalidEnterpriseModule("Enterprise modules require certification evidence")


class OrganizationalThreadPolicy:
    """P11 invariant: enterprise work has complete resource and schedule lineage."""

    def require_thread_lineage(self, thread: OrganizationalThread) -> None:
        if not thread.owner_id.strip():
            raise InvalidOrganizationalThread("Organizational threads require an owner")
        if thread.root_resource_id not in thread.resource_sequence:
            raise InvalidOrganizationalThread("Thread root resource must be in the lineage")
        if len(thread.resource_sequence) < 2:
            raise InvalidOrganizationalThread("Thread lineage requires multiple resources")
        if not thread.schedule_sequence:
            raise InvalidOrganizationalThread("Thread lineage requires scheduled work")
        if len(thread.resource_sequence) != len(set(thread.resource_sequence)):
            raise InvalidOrganizationalThread("Thread resources must be unique")
        if len(thread.schedule_sequence) != len(set(thread.schedule_sequence)):
            raise InvalidOrganizationalThread("Thread schedules must be unique")
        if not thread.evidence:
            raise InvalidOrganizationalThread("Thread lineage requires evidence")


class OperatingMaturityPolicy:
    """P11 invariant: maturity claims are evidence-bound and cover the enterprise."""

    def require_evidence_bound_coverage(self, snapshot: OperatingMaturitySnapshot) -> None:
        if snapshot.maturity_level < 1 or snapshot.maturity_level > 5:
            raise InvalidOperatingMaturity("Maturity level must be between 1 and 5")
        if len(snapshot.evidence) < snapshot.maturity_level:
            raise InvalidOperatingMaturity("Maturity level cannot exceed supporting evidence")
        if snapshot.module_count < 1:
            raise InvalidOperatingMaturity("Operating maturity requires registered modules")
        if snapshot.active_thread_count < 0:
            raise InvalidOperatingMaturity("Active thread count cannot be negative")
        missing = set(EnterpriseResourceType) - set(snapshot.covered_resource_types)
        if missing:
            names = ", ".join(sorted(item.value for item in missing))
            raise InvalidOperatingMaturity("Resource coverage is incomplete: " + names)
