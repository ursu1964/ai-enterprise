from pathlib import PurePosixPath


class RepositoryScopeError(ValueError):
    pass


def normalize_repository_scope(value: str) -> str:
    candidate = value.replace("\\", "/").strip()
    if not candidate or candidate.startswith(("/", "~/")):
        raise RepositoryScopeError("Repository scope must be relative")
    parts = PurePosixPath(candidate).parts
    if ".." in parts or "." in parts:
        raise RepositoryScopeError("Repository scope contains traversal")
    normalized = PurePosixPath(*parts).as_posix()
    if normalized in {"*", "**", "**/*"}:
        raise RepositoryScopeError("Repository-wide wildcard is prohibited")
    return normalized


def validate_repository_scope(
    value: str,
    *,
    indexed_paths: frozenset[str],
    proposed_paths: frozenset[str] = frozenset(),
    protected_paths: tuple[str, ...] = (".git", ".github/workflows", "infra/production"),
) -> str:
    scope = normalize_repository_scope(value)
    literal = scope.removesuffix("/**").removesuffix("/*")
    if any(literal == path or literal.startswith(f"{path}/") for path in protected_paths):
        raise RepositoryScopeError("Repository scope is protected")
    exists = literal in indexed_paths or any(
        path.startswith(f"{literal}/") for path in indexed_paths
    )
    proposed = literal in proposed_paths
    if not exists and not proposed:
        raise RepositoryScopeError("Repository scope is fabricated or absent")
    return scope


def scopes_overlap(first: str, second: str) -> bool:
    left = normalize_repository_scope(first).removesuffix("/**").removesuffix("/*")
    right = normalize_repository_scope(second).removesuffix("/**").removesuffix("/*")
    return left == right or left.startswith(f"{right}/") or right.startswith(f"{left}/")
