from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, SecretStr

from ai_enterprise.domain.r9_uak import (
    UakKernelEvent,
    UakSchedulePlan,
    UakSdkContract,
    UakSubsystem,
    kernel_event,
)
from ai_enterprise.domain.specification.kernel import specification_hash


class KernelRuntimeError(ValueError):
    pass


class KernelReplayEntry(BaseModel):
    model_config = ConfigDict(frozen=True)

    record_id: str
    event_type: str
    source_subsystem: str
    target_subsystem: str
    object_identity: str
    event_hash: str
    causation_hash: str | None


class KernelScheduleDispatch(BaseModel):
    model_config = ConfigDict(frozen=True)

    schedule_id: str
    work_type: str
    target_subsystem: str
    event: UakKernelEvent


class SdkPackageMaterialization(BaseModel):
    model_config = ConfigDict(frozen=True)

    package_root: str
    package_ref: str
    language: str
    contract_hash: str
    package_hash: str
    files: tuple[str, ...]


class R9OperationalBackendCheck(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    configured: bool
    ready: bool
    detail: str
    required: tuple[str, ...] = ()


class R9OperationalReadiness(BaseModel):
    model_config = ConfigDict(frozen=True)

    event_bus_backend: str
    event_bus_ready: bool
    worker_fleet_ready: bool
    sdk_registry_backend: str
    sdk_registry_ready: bool
    ready: bool
    checks: tuple[R9OperationalBackendCheck, ...]


class SdkRegistryPublication(BaseModel):
    model_config = ConfigDict(frozen=True)

    backend: str
    registry_ref: str
    package_root: str
    package_hash: str
    publication_ref: str
    ready: bool
    published: bool
    command: tuple[str, ...] = ()
    detail: str


@dataclass(frozen=True, slots=True)
class KernelRecordView:
    record_type: str
    record_id: str
    status: str
    record_document: dict[str, Any]
    record_hash: str


def replay_kernel_events(records: list[KernelRecordView]) -> tuple[KernelReplayEntry, ...]:
    known_hashes: set[str] = set()
    entries: list[KernelReplayEntry] = []
    for record in records:
        if record.record_type != "event":
            known_hashes.add(record.record_hash)
            continue
        try:
            event = UakKernelEvent.model_validate(record.record_document)
        except ValueError as exc:
            raise KernelRuntimeError("kernel event document is not replayable") from exc
        if record.record_hash != event.event_hash:
            raise KernelRuntimeError("kernel event record hash does not match event hash")
        if event.causation_hash is not None and event.causation_hash not in known_hashes:
            raise KernelRuntimeError("kernel event causation hash is not replayable")
        known_hashes.add(record.record_hash)
        entries.append(
            KernelReplayEntry(
                record_id=record.record_id,
                event_type=event.event_type,
                source_subsystem=event.source_subsystem.value,
                target_subsystem=event.target_subsystem.value,
                object_identity=event.object_identity,
                event_hash=event.event_hash,
                causation_hash=event.causation_hash,
            )
        )
    return tuple(entries)


def dispatch_ready_schedules(
    records: list[KernelRecordView],
    *,
    start_event_index: int,
) -> tuple[KernelScheduleDispatch, ...]:
    existing_dispatch_identities = {
        item.record_document.get("object_identity")
        for item in records
        if item.record_type == "event"
    }
    dispatches: list[KernelScheduleDispatch] = []
    next_index = start_event_index
    for record in records:
        if record.record_type != "schedule" or record.status != "dispatchable":
            continue
        schedule = UakSchedulePlan.model_validate(record.record_document)
        dispatch_identity = f"schedule:{schedule.schedule_id}:dispatch"
        if dispatch_identity in existing_dispatch_identities:
            continue
        event = kernel_event(
            index=next_index,
            event_type=f"{schedule.work_type}.dispatch_requested",
            source_subsystem=UakSubsystem.KERNEL_CORE,
            target_subsystem=_target_for_work_type(schedule.work_type),
            object_identity=dispatch_identity,
            payload_hash=schedule.schedule_hash,
            causation_hash=schedule.schedule_hash,
        )
        dispatches.append(
            KernelScheduleDispatch(
                schedule_id=schedule.schedule_id,
                work_type=schedule.work_type,
                target_subsystem=event.target_subsystem.value,
                event=event,
            )
        )
        existing_dispatch_identities.add(dispatch_identity)
        next_index += 1
    return tuple(dispatches)


def materialize_sdk_package(
    contract: UakSdkContract,
    output_root: Path,
) -> SdkPackageMaterialization:
    safe_name = f"{contract.language.value}-{contract.contract_version}".replace("/", "-")
    package_root = (output_root / safe_name).resolve()
    output_root_resolved = output_root.resolve()
    if output_root_resolved not in package_root.parents and package_root != output_root_resolved:
        raise KernelRuntimeError("SDK package path escapes output root")
    package_root.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema_version": "uak-sdk-package-0.1",
        "language": contract.language.value,
        "contract_version": contract.contract_version,
        "api_surfaces": list(contract.api_surfaces),
        "canonical_contract_hash": contract.canonical_contract_hash,
        "package_ref": contract.package_ref,
        "sdk_hash": contract.sdk_hash,
    }
    files = {
        "kernel-sdk.json": json.dumps(manifest, sort_keys=True, indent=2) + "\n",
        "README.md": _readme(contract),
        **_language_stub(contract),
        **_package_metadata(contract),
    }
    for relative_path, content in files.items():
        target = package_root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    package_hash = specification_hash(
        {
            "package_ref": contract.package_ref,
            "files": {path: files[path] for path in sorted(files)},
        }
    )
    return SdkPackageMaterialization(
        package_root=str(package_root),
        package_ref=contract.package_ref,
        language=contract.language.value,
        contract_hash=contract.sdk_hash,
        package_hash=package_hash,
        files=tuple(sorted(files)),
    )


def r9_operational_readiness(
    settings: object,
    *,
    repo_root: Path | None = None,
) -> R9OperationalReadiness:
    event_bus_backend = str(getattr(settings, "r9_event_bus_backend", "local"))
    sdk_registry_backend = str(getattr(settings, "r9_sdk_registry_backend", "filesystem"))
    checks = [
        _event_bus_check(settings, event_bus_backend),
        _worker_fleet_check(settings, repo_root=repo_root),
        _sdk_registry_check(settings, sdk_registry_backend),
    ]
    event_bus_ready = checks[0].ready
    worker_fleet_ready = checks[1].ready
    sdk_registry_ready = checks[2].ready
    return R9OperationalReadiness(
        event_bus_backend=event_bus_backend,
        event_bus_ready=event_bus_ready,
        worker_fleet_ready=worker_fleet_ready,
        sdk_registry_backend=sdk_registry_backend,
        sdk_registry_ready=sdk_registry_ready,
        ready=event_bus_ready and worker_fleet_ready and sdk_registry_ready,
        checks=tuple(checks),
    )


def publish_sdk_package_to_registry(
    materialization: SdkPackageMaterialization,
    settings: object,
    *,
    dry_run: bool = True,
) -> SdkRegistryPublication:
    backend = str(getattr(settings, "r9_sdk_registry_backend", "filesystem"))
    package_root = Path(materialization.package_root)
    if not package_root.exists() or not package_root.is_dir():
        raise KernelRuntimeError("SDK package has not been materialized on disk")
    if backend == "filesystem":
        return SdkRegistryPublication(
            backend=backend,
            registry_ref=str(getattr(settings, "r9_sdk_registry_ref", None) or package_root.parent),
            package_root=str(package_root),
            package_hash=materialization.package_hash,
            publication_ref=f"file://{package_root}",
            ready=True,
            published=True,
            detail="SDK package is physically available in the configured artifact root",
        )
    if backend != "npm":
        raise KernelRuntimeError(f"unsupported R9 SDK registry backend: {backend}")
    registry_ref = getattr(settings, "r9_sdk_registry_ref", None)
    if not registry_ref:
        return SdkRegistryPublication(
            backend=backend,
            registry_ref="",
            package_root=str(package_root),
            package_hash=materialization.package_hash,
            publication_ref="",
            ready=False,
            published=False,
            detail="R9_SDK_REGISTRY_REF must be configured for npm publication",
        )
    if not (package_root / "package.json").exists():
        return SdkRegistryPublication(
            backend=backend,
            registry_ref=str(registry_ref),
            package_root=str(package_root),
            package_hash=materialization.package_hash,
            publication_ref="",
            ready=False,
            published=False,
            detail="npm publication requires a TypeScript SDK package with package.json",
        )
    npm_bin = shutil.which("npm")
    command = ("npm", "publish", "--registry", str(registry_ref))
    credential_ready = _npm_credentials_configured(settings)
    if npm_bin is None or not credential_ready:
        missing = []
        if npm_bin is None:
            missing.append("npm CLI")
        if not credential_ready:
            missing.append("npm token or npmrc")
        return SdkRegistryPublication(
            backend=backend,
            registry_ref=str(registry_ref),
            package_root=str(package_root),
            package_hash=materialization.package_hash,
            publication_ref="",
            ready=False,
            published=False,
            command=command,
            detail=f"npm publication is not ready; missing {', '.join(missing)}",
        )
    if dry_run:
        return SdkRegistryPublication(
            backend=backend,
            registry_ref=str(registry_ref),
            package_root=str(package_root),
            package_hash=materialization.package_hash,
            publication_ref=f"npm://{registry_ref}/{materialization.package_ref}",
            ready=True,
            published=False,
            command=command,
            detail="npm publication readiness passed; dry_run prevented external publish",
        )
    env = _npm_publish_env(settings)
    completed = subprocess.run(
        command,
        cwd=package_root,
        env=env,
        text=True,
        capture_output=True,
        timeout=120,
        check=False,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "npm publish failed").strip()
        raise KernelRuntimeError(detail[:500])
    return SdkRegistryPublication(
        backend=backend,
        registry_ref=str(registry_ref),
        package_root=str(package_root),
        package_hash=materialization.package_hash,
        publication_ref=f"npm://{registry_ref}/{materialization.package_ref}",
        ready=True,
        published=True,
        command=command,
        detail="npm publish completed",
    )


def _target_for_work_type(work_type: str) -> UakSubsystem:
    if work_type.startswith(("manifest", "validation")):
        return UakSubsystem.MANIFEST_MANAGER
    if work_type.startswith(("transform", "transformation")):
        return UakSubsystem.TRANSFORMATION_MANAGER
    if work_type.startswith(("artifact", "generation", "generator")):
        return UakSubsystem.ARTIFACT_MANAGER
    if work_type.startswith("deployment"):
        return UakSubsystem.DEPLOYMENT_MANAGER
    if work_type.startswith(("runtime", "execution")):
        return UakSubsystem.RUNTIME_MANAGER
    if work_type.startswith(("governance", "simulation")):
        return UakSubsystem.GOVERNANCE_MANAGER
    if work_type.startswith("ai"):
        return UakSubsystem.AI_MANAGER
    return UakSubsystem.PLUGIN_MANAGER


def _readme(contract: UakSdkContract) -> str:
    surfaces = "\n".join(f"- {surface}" for surface in contract.api_surfaces)
    return (
        f"# AI Enterprise Kernel SDK ({contract.language.value})\n\n"
        f"Contract version: `{contract.contract_version}`\n\n"
        f"Package ref: `{contract.package_ref}`\n\n"
        "API surfaces:\n\n"
        f"{surfaces}\n"
    )


def _language_stub(contract: UakSdkContract) -> dict[str, str]:
    surfaces = ", ".join(contract.api_surfaces)
    if contract.language.value == "python":
        return {
            "ai_enterprise_kernel_sdk/__init__.py": (
                f'CONTRACT_VERSION = "{contract.contract_version}"\n'
                f'API_SURFACES = {tuple(contract.api_surfaces)!r}\n'
            )
        }
    if contract.language.value == "typescript":
        return {
            "src/index.ts": (
                f'export const contractVersion = "{contract.contract_version}";\n'
                f"export const apiSurfaces = {json.dumps(list(contract.api_surfaces))};\n"
            )
        }
    return {
        "CONTRACT.txt": (
            f"language={contract.language.value}\n"
            f"contract_version={contract.contract_version}\n"
            f"api_surfaces={surfaces}\n"
        )
    }


def _package_metadata(contract: UakSdkContract) -> dict[str, str]:
    if contract.language.value != "typescript":
        return {}
    package_name = _npm_package_name(contract.package_ref)
    return {
        "package.json": json.dumps(
            {
                "name": package_name,
                "version": contract.contract_version,
                "private": False,
                "type": "module",
                "main": "src/index.ts",
                "files": ["src", "kernel-sdk.json", "README.md"],
            },
            sort_keys=True,
            indent=2,
        )
        + "\n"
    }


def _event_bus_check(settings: object, backend: str) -> R9OperationalBackendCheck:
    endpoint = getattr(settings, "r9_event_bus_endpoint", None)
    topic = getattr(settings, "r9_event_bus_topic", None)
    region = getattr(settings, "r9_event_bus_region", None)
    credentials_ref = getattr(settings, "r9_event_bus_credentials_ref", None)
    if backend == "local":
        return R9OperationalBackendCheck(
            name="event_bus",
            configured=True,
            ready=True,
            detail="using durable local DB-backed kernel events",
        )
    if backend == "kafka":
        required = ("R9_EVENT_BUS_ENDPOINT", "R9_EVENT_BUS_TOPIC")
        ready = bool(endpoint and topic)
        return R9OperationalBackendCheck(
            name="event_bus",
            configured=ready,
            ready=ready,
            detail=(
                "Kafka bootstrap endpoint and topic configured"
                if ready
                else "Kafka backend requires bootstrap endpoint and topic"
            ),
            required=required,
        )
    if backend == "sqs":
        required = (
            "R9_EVENT_BUS_ENDPOINT",
            "R9_EVENT_BUS_TOPIC",
            "R9_EVENT_BUS_REGION",
            "R9_EVENT_BUS_CREDENTIALS_REF",
        )
        ready = bool(endpoint and topic and region and credentials_ref)
        return R9OperationalBackendCheck(
            name="event_bus",
            configured=ready,
            ready=ready,
            detail=(
                "SQS queue endpoint, queue/topic, region, and credential reference configured"
                if ready
                else (
                    "SQS backend requires queue endpoint, queue/topic, region, "
                    "and credential reference"
                )
            ),
            required=required,
        )
    if backend == "nats":
        required = ("R9_EVENT_BUS_ENDPOINT", "R9_EVENT_BUS_TOPIC")
        ready = bool(endpoint and topic)
        return R9OperationalBackendCheck(
            name="event_bus",
            configured=ready,
            ready=ready,
            detail=(
                "NATS server endpoint and subject configured"
                if ready
                else "NATS backend requires server endpoint and subject"
            ),
            required=required,
        )
    return R9OperationalBackendCheck(
        name="event_bus",
        configured=False,
        ready=False,
        detail=f"unsupported R9 event bus backend: {backend}",
    )


def _worker_fleet_check(
    settings: object,
    *,
    repo_root: Path | None,
) -> R9OperationalBackendCheck:
    configured_path = getattr(settings, "r9_worker_fleet_manifest_path", None)
    default_root = repo_root or Path(__file__).resolve().parents[4]
    manifest_path = Path(
        configured_path or default_root / "deploy/kubernetes/worker-deployment.yaml"
    )
    if not manifest_path.is_absolute():
        manifest_path = default_root / manifest_path
    if not manifest_path.exists():
        return R9OperationalBackendCheck(
            name="worker_fleet",
            configured=False,
            ready=False,
            detail=f"worker fleet manifest not found: {manifest_path}",
            required=("R9_WORKER_FLEET_MANIFEST_PATH",),
        )
    text = manifest_path.read_text(encoding="utf-8")
    ready = "kind: Deployment" in text and "worker" in text.lower()
    return R9OperationalBackendCheck(
        name="worker_fleet",
        configured=True,
        ready=ready,
        detail=(
            f"worker fleet deployment manifest is present: {manifest_path}"
            if ready
            else f"manifest does not look like a worker Deployment: {manifest_path}"
        ),
        required=("R9_WORKER_FLEET_MANIFEST_PATH",),
    )


def _sdk_registry_check(settings: object, backend: str) -> R9OperationalBackendCheck:
    if backend == "filesystem":
        artifact_root = Path(getattr(settings, "artifact_root", Path("./artifacts")))
        return R9OperationalBackendCheck(
            name="sdk_registry",
            configured=True,
            ready=True,
            detail=f"filesystem SDK publication uses artifact root: {artifact_root}",
        )
    if backend == "npm":
        registry_ref = getattr(settings, "r9_sdk_registry_ref", None)
        npm_bin = shutil.which("npm")
        credential_ready = _npm_credentials_configured(settings)
        ready = bool(registry_ref and npm_bin and credential_ready)
        missing = []
        if not registry_ref:
            missing.append("R9_SDK_REGISTRY_REF")
        if npm_bin is None:
            missing.append("npm CLI")
        if not credential_ready:
            missing.append("npm token or npmrc")
        return R9OperationalBackendCheck(
            name="sdk_registry",
            configured=bool(registry_ref),
            ready=ready,
            detail=(
                "npm registry, CLI, and credentials configured"
                if ready
                else f"npm SDK registry is not ready; missing {', '.join(missing)}"
            ),
            required=(
                "R9_SDK_REGISTRY_REF",
                "R6_PUBLICATION_NPM_TOKEN or R6_PUBLICATION_NPMRC_PATH",
            ),
        )
    return R9OperationalBackendCheck(
        name="sdk_registry",
        configured=False,
        ready=False,
        detail=f"unsupported R9 SDK registry backend: {backend}",
    )


def _npm_credentials_configured(settings: object) -> bool:
    token = getattr(settings, "r6_publication_npm_token", None)
    npmrc_path = getattr(settings, "r6_publication_npmrc_path", None)
    if isinstance(token, SecretStr) and token.get_secret_value():
        return True
    if isinstance(token, str) and token:
        return True
    if npmrc_path and Path(npmrc_path).exists():
        return True
    return bool(os.getenv("NPM_TOKEN"))


def _npm_publish_env(settings: object) -> dict[str, str]:
    env = dict(os.environ)
    token = getattr(settings, "r6_publication_npm_token", None)
    if isinstance(token, SecretStr) and token.get_secret_value():
        env["NPM_TOKEN"] = token.get_secret_value()
    elif isinstance(token, str) and token:
        env["NPM_TOKEN"] = token
    npmrc_path = getattr(settings, "r6_publication_npmrc_path", None)
    if npmrc_path and Path(npmrc_path).exists():
        env["NPM_CONFIG_USERCONFIG"] = str(npmrc_path)
    return env


def _npm_package_name(package_ref: str) -> str:
    name = package_ref
    if "://" in name:
        name = name.split("://", 1)[1]
    if "/" in name:
        name = name.rsplit("/", 1)[1]
    if "@" in name and not name.startswith("@"):
        name = name.split("@", 1)[0]
    return name or "ai-enterprise-kernel-sdk"
