from dataclasses import dataclass
from pathlib import PurePosixPath


@dataclass(frozen=True, slots=True)
class DependencyManifest:
    path: str
    type: str


MANIFEST_TYPES = {
    "pyproject.toml": "python-pyproject",
    "requirements.txt": "python-requirements",
    "poetry.lock": "python-poetry-lock",
    "uv.lock": "python-uv-lock",
    "package.json": "node-package",
    "package-lock.json": "node-package-lock",
    "pnpm-lock.yaml": "node-pnpm-lock",
    "yarn.lock": "node-yarn-lock",
    "go.mod": "go-modules",
    "Cargo.toml": "rust-cargo",
    "pom.xml": "java-maven",
    "build.gradle": "java-gradle",
}


def scan_dependency_manifests(paths: list[str]) -> tuple[DependencyManifest, ...]:
    values = [
        DependencyManifest(path, MANIFEST_TYPES[PurePosixPath(path).name])
        for path in paths
        if PurePosixPath(path).name in MANIFEST_TYPES
    ]
    return tuple(sorted(values, key=lambda item: item.path))
