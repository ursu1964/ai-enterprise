from enum import StrEnum


class EnterpriseResourceType(StrEnum):
    PROJECT = "project"
    REPOSITORY = "repository"
    REQUIREMENT = "requirement"
    ARCHITECTURE = "architecture"
    DECISION_RECORD = "decision_record"
    RISK = "risk"
    WORK_PACKAGE = "work_package"
    EXECUTION = "execution"
    PATCH = "patch"
    REVIEW = "review"
    APPROVAL = "approval"
    DEPLOYMENT = "deployment"
    ENVIRONMENT = "environment"
    EVIDENCE = "evidence"
    AGENT = "agent"
    CREW = "crew"
    CAPABILITY = "capability"
    POLICY = "policy"
    KNOWLEDGE_ARTIFACT = "knowledge_artifact"
    SERVICE = "service"
    INFRASTRUCTURE = "infrastructure"
    CUSTOMER = "customer"
    PRODUCT = "product"
    PORTFOLIO = "portfolio"


class EnterpriseResourceState(StrEnum):
    REGISTERED = "registered"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    RETIRED = "retired"


class EnterpriseScheduleState(StrEnum):
    QUEUED = "queued"
    BLOCKED = "blocked"
    DISPATCHABLE = "dispatchable"
    CANCELLED = "cancelled"


class EnterpriseModuleState(StrEnum):
    REGISTERED = "registered"
    CERTIFIED = "certified"
    SUSPENDED = "suspended"
    RETIRED = "retired"


class OrganizationalThreadState(StrEnum):
    OPEN = "open"
    BLOCKED = "blocked"
    COMPLETE = "complete"
    CANCELLED = "cancelled"
