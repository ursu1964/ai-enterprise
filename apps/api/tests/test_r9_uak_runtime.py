from pathlib import Path
from types import SimpleNamespace

import pytest

from ai_enterprise.application.r9_uak_runtime import (
    KernelRecordView,
    KernelRuntimeError,
    dispatch_ready_schedules,
    materialize_sdk_package,
    publish_sdk_package_to_registry,
    r9_operational_readiness,
    replay_kernel_events,
)
from ai_enterprise.domain.r9_uak import (
    UakSdkLanguage,
    UakSubsystem,
    kernel_event,
    schedule_plan,
    sdk_contract,
)


def test_r9_runtime_replays_verified_kernel_events_in_order() -> None:
    first = kernel_event(
        index=1,
        event_type="manifest.updated",
        source_subsystem=UakSubsystem.KERNEL_CORE,
        target_subsystem=UakSubsystem.TRANSFORMATION_MANAGER,
        object_identity="manifest:orders:v2",
        payload_hash="a" * 64,
    )
    second = kernel_event(
        index=2,
        event_type="transformation.requested",
        source_subsystem=UakSubsystem.KERNEL_CORE,
        target_subsystem=UakSubsystem.TRANSFORMATION_MANAGER,
        object_identity="manifest:orders:v2",
        payload_hash="b" * 64,
        causation_hash=first.event_hash,
    )

    replay = replay_kernel_events(
        [
            KernelRecordView(
                record_type="event",
                record_id=first.event_id,
                status="recorded",
                record_document=first.model_dump(mode="json"),
                record_hash=first.event_hash,
            ),
            KernelRecordView(
                record_type="event",
                record_id=second.event_id,
                status="recorded",
                record_document=second.model_dump(mode="json"),
                record_hash=second.event_hash,
            ),
        ]
    )

    assert [entry.event_type for entry in replay] == [
        "manifest.updated",
        "transformation.requested",
    ]
    assert replay[1].causation_hash == first.event_hash


def test_r9_runtime_blocks_corrupt_or_unreplayable_events() -> None:
    event = kernel_event(
        index=1,
        event_type="manifest.updated",
        source_subsystem=UakSubsystem.KERNEL_CORE,
        target_subsystem=UakSubsystem.TRANSFORMATION_MANAGER,
        object_identity="manifest:orders:v2",
        payload_hash="a" * 64,
        causation_hash="b" * 64,
    )

    with pytest.raises(KernelRuntimeError, match="causation hash"):
        replay_kernel_events(
            [
                KernelRecordView(
                    record_type="event",
                    record_id=event.event_id,
                    status="recorded",
                    record_document=event.model_dump(mode="json"),
                    record_hash=event.event_hash,
                )
            ]
        )

    valid = kernel_event(
        index=2,
        event_type="manifest.updated",
        source_subsystem=UakSubsystem.KERNEL_CORE,
        target_subsystem=UakSubsystem.TRANSFORMATION_MANAGER,
        object_identity="manifest:orders:v2",
        payload_hash="a" * 64,
    )
    with pytest.raises(KernelRuntimeError, match="record hash"):
        replay_kernel_events(
            [
                KernelRecordView(
                    record_type="event",
                    record_id=valid.event_id,
                    status="recorded",
                    record_document=valid.model_dump(mode="json"),
                    record_hash="c" * 64,
                )
            ]
        )


def test_r9_runtime_dispatches_ready_schedules_once() -> None:
    blocked = schedule_plan(
        index=1,
        work_type="artifact.generation",
        object_identity="manifest:orders:v2",
        dependencies=("transform:orders",),
        unsatisfied_dependencies=("transform:orders",),
        resource_claims={"compute": 2.0},
    )
    ready = schedule_plan(
        index=2,
        work_type="artifact.generation",
        object_identity="manifest:orders:v2",
        dependencies=("transform:orders",),
        resource_claims={"compute": 2.0},
    )
    views = [
        KernelRecordView(
            record_type="schedule",
            record_id=blocked.schedule_id,
            status=blocked.status.value,
            record_document=blocked.model_dump(mode="json"),
            record_hash=blocked.schedule_hash,
        ),
        KernelRecordView(
            record_type="schedule",
            record_id=ready.schedule_id,
            status=ready.status.value,
            record_document=ready.model_dump(mode="json"),
            record_hash=ready.schedule_hash,
        ),
    ]

    dispatches = dispatch_ready_schedules(views, start_event_index=1)

    assert len(dispatches) == 1
    assert dispatches[0].schedule_id == ready.schedule_id
    assert dispatches[0].target_subsystem == UakSubsystem.ARTIFACT_MANAGER.value
    assert dispatches[0].event.payload_hash == ready.schedule_hash

    existing = KernelRecordView(
        record_type="event",
        record_id=dispatches[0].event.event_id,
        status="recorded",
        record_document=dispatches[0].event.model_dump(mode="json"),
        record_hash=dispatches[0].event.event_hash,
    )
    assert dispatch_ready_schedules([*views, existing], start_event_index=2) == ()


def test_r9_runtime_materializes_physical_sdk_package(tmp_path: Path) -> None:
    contract = sdk_contract(
        index=1,
        language=UakSdkLanguage.PYTHON,
        contract_version="1.0",
        api_surfaces=("manifest", "runtime", "governance"),
        canonical_contract_hash="d" * 64,
        package_ref="pypi://ai-enterprise-kernel-sdk@1.0",
    )

    result = materialize_sdk_package(contract, tmp_path)

    package_root = Path(result.package_root)
    assert (package_root / "kernel-sdk.json").exists()
    assert (package_root / "README.md").exists()
    assert (package_root / "ai_enterprise_kernel_sdk/__init__.py").exists()
    assert result.package_hash
    assert result.files == (
        "README.md",
        "ai_enterprise_kernel_sdk/__init__.py",
        "kernel-sdk.json",
    )


def test_r9_runtime_materializes_typescript_sdk_package_metadata(tmp_path: Path) -> None:
    contract = sdk_contract(
        index=1,
        language=UakSdkLanguage.TYPESCRIPT,
        contract_version="1.2.3",
        api_surfaces=("manifest", "runtime"),
        canonical_contract_hash="e" * 64,
        package_ref="npm://registry.example.test/@acme/ai-enterprise-kernel-sdk@1.2.3",
    )

    result = materialize_sdk_package(contract, tmp_path)

    package_root = Path(result.package_root)
    assert (package_root / "package.json").exists()
    assert (package_root / "src/index.ts").exists()
    assert "package.json" in result.files


def test_r9_operational_readiness_defaults_to_local_event_bus_and_filesystem_registry(
    tmp_path: Path,
) -> None:
    manifest = tmp_path / "worker-deployment.yaml"
    manifest.write_text("apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: worker\n")
    settings = SimpleNamespace(
        artifact_root=tmp_path / "artifacts",
        r9_event_bus_backend="local",
        r9_worker_fleet_manifest_path=manifest,
        r9_sdk_registry_backend="filesystem",
    )

    readiness = r9_operational_readiness(settings, repo_root=tmp_path)

    assert readiness.ready is True
    assert readiness.event_bus_ready is True
    assert readiness.worker_fleet_ready is True
    assert readiness.sdk_registry_ready is True


@pytest.mark.parametrize(
    ("backend", "configured"),
    [
        ("kafka", {"endpoint": "kafka:9092", "topic": "uak-events"}),
        (
            "sqs",
            {
                "endpoint": "https://sqs.us-east-1.amazonaws.com/123/uak",
                "topic": "uak-events",
                "region": "us-east-1",
                "credentials_ref": "iam-role://ai-enterprise",
            },
        ),
        ("nats", {"endpoint": "nats://nats:4222", "topic": "uak.events"}),
    ],
)
def test_r9_event_bus_readiness_requires_external_backend_configuration(
    backend: str,
    configured: dict[str, str],
    tmp_path: Path,
) -> None:
    manifest = tmp_path / "worker-deployment.yaml"
    manifest.write_text("kind: Deployment\nmetadata:\n  name: worker\n")
    missing = SimpleNamespace(
        artifact_root=tmp_path,
        r9_event_bus_backend=backend,
        r9_worker_fleet_manifest_path=manifest,
        r9_sdk_registry_backend="filesystem",
    )
    ready = SimpleNamespace(
        artifact_root=tmp_path,
        r9_event_bus_backend=backend,
        r9_event_bus_endpoint=configured.get("endpoint"),
        r9_event_bus_topic=configured.get("topic"),
        r9_event_bus_region=configured.get("region"),
        r9_event_bus_credentials_ref=configured.get("credentials_ref"),
        r9_worker_fleet_manifest_path=manifest,
        r9_sdk_registry_backend="filesystem",
    )

    assert r9_operational_readiness(missing, repo_root=tmp_path).event_bus_ready is False
    assert r9_operational_readiness(ready, repo_root=tmp_path).event_bus_ready is True


def test_r9_sdk_publication_records_filesystem_publication(tmp_path: Path) -> None:
    contract = sdk_contract(
        index=1,
        language=UakSdkLanguage.PYTHON,
        contract_version="1.0",
        api_surfaces=("manifest", "runtime"),
        canonical_contract_hash="f" * 64,
        package_ref="pypi://ai-enterprise-kernel-sdk@1.0",
    )
    materialization = materialize_sdk_package(contract, tmp_path)
    settings = SimpleNamespace(r9_sdk_registry_backend="filesystem", r9_sdk_registry_ref=None)

    publication = publish_sdk_package_to_registry(materialization, settings)

    assert publication.ready is True
    assert publication.published is True
    assert publication.publication_ref.startswith("file://")


def test_r9_sdk_publication_dry_run_validates_npm_without_leaking_credentials(
    tmp_path: Path,
) -> None:
    contract = sdk_contract(
        index=1,
        language=UakSdkLanguage.TYPESCRIPT,
        contract_version="1.0.0",
        api_surfaces=("manifest", "runtime"),
        canonical_contract_hash="1" * 64,
        package_ref="npm://registry.example.test/ai-enterprise-kernel-sdk@1.0.0",
    )
    materialization = materialize_sdk_package(contract, tmp_path)
    settings = SimpleNamespace(
        r9_sdk_registry_backend="npm",
        r9_sdk_registry_ref="https://registry.example.test",
        r6_publication_npm_token="secret-token",
        r6_publication_npmrc_path=None,
    )

    publication = publish_sdk_package_to_registry(materialization, settings, dry_run=True)

    assert publication.published is False
    assert publication.command == ("npm", "publish", "--registry", "https://registry.example.test")
    assert "secret-token" not in publication.model_dump_json()
