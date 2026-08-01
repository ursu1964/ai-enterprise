from .entities import EnterpriseResource, EnterpriseSchedule
from .exceptions import InvalidEnterpriseResource, InvalidEnterpriseSchedule


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
