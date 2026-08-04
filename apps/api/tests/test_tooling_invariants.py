import importlib.util
import os
from pathlib import Path


def _load_tool():
    root = Path(__file__).resolve().parents[3]
    path = root / "tools" / "check_tooling_invariants.py"
    spec = importlib.util.spec_from_file_location("check_tooling_invariants", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


tooling = _load_tool()


def _repository(tmp_path: Path, *, action: str = "actions/checkout@v5") -> Path:
    (tmp_path / "tools").mkdir()
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / ".github" / "workflows" / "verify.yml").write_text(
        f"steps:\n  - uses: {action}\n", encoding="utf-8"
    )
    return tmp_path


def test_tooling_invariants_accept_current_actions_and_executable_tools(tmp_path: Path) -> None:
    root = _repository(tmp_path)
    script = root / "tools" / "verify.py"
    script.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
    script.chmod(script.stat().st_mode | 0o111)

    report = tooling.check_tooling_invariants(root)

    assert report["conformant"] is True
    assert report["findings"] == []


def test_tooling_invariants_reject_non_executable_shebang_tool(tmp_path: Path) -> None:
    root = _repository(tmp_path)
    script = root / "tools" / "verify.py"
    script.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
    script.chmod(script.stat().st_mode & ~0o111)

    report = tooling.check_tooling_invariants(root)

    assert report["conformant"] is False
    assert report["findings"] == ["tools/verify.py: shebang script is not executable"]
    assert not os.access(script, os.X_OK)


def test_tooling_invariants_reject_outdated_known_action(tmp_path: Path) -> None:
    root = _repository(tmp_path, action="actions/setup-python@v5")

    report = tooling.check_tooling_invariants(root)

    assert report["conformant"] is False
    assert "required v6" in report["findings"][0]
