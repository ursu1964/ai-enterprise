from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, replace
from pathlib import Path

from .dependency_scanner import DependencyManifest, scan_dependency_manifests
from .git_snapshot import RepositorySnapshotResult
from .language_detection import detect_language

EXCLUDED_PARTS = frozenset(
    {
        ".git",
        "node_modules",
        ".venv",
        "venv",
        "dist",
        "build",
        "coverage",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "vendor",
    }
)
SECRET_NAMES = frozenset(
    {".env", ".npmrc", ".pypirc", "credentials", "credentials.json", "id_rsa", "id_ed25519"}
)
PROTECTED_PATHS = (".git", ".github/workflows", "infra/production")


@dataclass(frozen=True, slots=True)
class IndexedFile:
    path: str
    kind: str
    language: str | None
    size_bytes: int
    content_hash: str


@dataclass(frozen=True, slots=True)
class RepositoryModule:
    module_key: str
    root_path: str
    language: str
    build_system: str
    test_frameworks: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RepositoryIndex:
    schema_version: int
    base_commit_sha: str
    tree_hash: str
    roots: tuple[str, ...]
    files: tuple[IndexedFile, ...]
    modules: tuple[RepositoryModule, ...]
    dependency_manifests: tuple[DependencyManifest, ...]
    migration_roots: tuple[str, ...]
    test_roots: tuple[str, ...]
    protected_paths: tuple[str, ...]
    index_hash: str

    def document(self, *, include_hash: bool = True) -> dict[str, object]:
        value: dict[str, object] = {
            "schema_version": self.schema_version,
            "snapshot": {
                "base_commit_sha": self.base_commit_sha,
                "tree_hash": self.tree_hash,
            },
            "roots": list(self.roots),
            "files": [asdict(item) for item in self.files],
            "modules": [asdict(item) for item in self.modules],
            "dependency_manifests": [asdict(item) for item in self.dependency_manifests],
            "migration_roots": list(self.migration_roots),
            "test_roots": list(self.test_roots),
            "protected_paths": list(self.protected_paths),
        }
        if include_hash:
            value["index_hash"] = self.index_hash
        return value


class RepositoryIndexBuilder:
    def build(self, snapshot: RepositorySnapshotResult) -> RepositoryIndex:
        root = snapshot.snapshot_path.resolve()
        files: list[IndexedFile] = []
        for path in root.rglob("*"):
            if not path.is_file() or path.is_symlink():
                continue
            relative = path.relative_to(root)
            if self._excluded(relative, path):
                continue
            content = path.read_bytes()
            files.append(
                IndexedFile(
                    relative.as_posix(),
                    "source" if detect_language(relative) else "file",
                    detect_language(relative),
                    len(content),
                    hashlib.sha256(content).hexdigest(),
                )
            )
        files.sort(key=lambda item: item.path)
        paths = [item.path for item in files]
        roots = tuple(sorted({path.split("/", 1)[0] for path in paths}))
        manifests = scan_dependency_manifests(paths)
        modules = self._modules(files, manifests)
        migration_roots = tuple(
            sorted({self._ancestor(path, "versions") for path in paths if "/versions/" in path})
        )
        test_roots = tuple(
            sorted({path.split("/", 1)[0] for path in paths if path.startswith("tests/")})
        )
        partial = RepositoryIndex(
            1,
            snapshot.base_commit_sha,
            snapshot.tree_hash,
            roots,
            tuple(files),
            modules,
            manifests,
            migration_roots,
            test_roots,
            tuple(sorted(PROTECTED_PATHS)),
            "",
        )
        digest = hashlib.sha256(
            json.dumps(
                partial.document(include_hash=False), sort_keys=True, separators=(",", ":")
            ).encode()
        ).hexdigest()
        return replace(partial, index_hash=digest)

    @staticmethod
    def _excluded(relative: Path, path: Path) -> bool:
        if set(relative.parts) & EXCLUDED_PARTS:
            return True
        if relative.name in SECRET_NAMES or relative.name.startswith(".env."):
            return True
        if path.stat().st_size > 5_000_000:
            return True
        prefix = path.read_bytes()[:8192]
        return b"\0" in prefix

    @staticmethod
    def _modules(
        files: list[IndexedFile], manifests: tuple[DependencyManifest, ...]
    ) -> tuple[RepositoryModule, ...]:
        values: list[RepositoryModule] = []
        for manifest in manifests:
            path = Path(manifest.path)
            root = path.parent.as_posix()
            root = "." if root == "." else root
            languages = sorted(
                {
                    item.language
                    for item in files
                    if item.language and (root == "." or item.path.startswith(f"{root}/"))
                }
            )
            language = languages[0] if languages else "unknown"
            tests = ("pytest",) if language == "python" else ()
            key = "repository-root" if root == "." else root.replace("/", "-")
            values.append(RepositoryModule(key, root, language, manifest.type, tests))
        unique = {item.module_key: item for item in values}
        return tuple(unique[key] for key in sorted(unique))

    @staticmethod
    def _ancestor(path: str, marker: str) -> str:
        parts = path.split("/")
        return "/".join(parts[: parts.index(marker) + 1])
