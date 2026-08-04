from pathlib import Path

from ai_enterprise.infrastructure.database.models import (
    CrewRunModel,
    JobModel,
    WorkPackageModel,
)


def test_dashboard_history_models_have_project_time_indexes() -> None:
    expected = {
        JobModel: "ix_jobs_project_created_at",
        CrewRunModel: "ix_crew_runs_project_created_at",
        WorkPackageModel: "ix_work_packages_project_created_at",
    }

    for model, index_name in expected.items():
        indexes = {
            index.name: tuple(column.name for column in index.columns)
            for index in model.__table__.indexes
        }
        assert indexes[index_name] == ("project_id", "created_at")


def test_dashboard_read_index_migration_is_reversible() -> None:
    root = Path(__file__).resolve().parents[3]
    migration = (
        root / "migrations/versions/f1b5c8d3e7a2_add_dashboard_read_path_indexes.py"
    ).read_text(encoding="utf-8")

    for name in (
        "ix_jobs_project_created_at",
        "ix_crew_runs_project_created_at",
        "ix_work_packages_project_created_at",
    ):
        assert f'op.create_index(\n        "{name}"' in migration
        assert f'op.drop_index("{name}"' in migration
