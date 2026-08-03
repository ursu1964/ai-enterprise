from __future__ import annotations

# ruff: noqa: E501 -- scripted implementation assets retain readable source lines.
import json
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any

from crewai import LLM

from ai_enterprise.config import Settings
from ai_enterprise.domain.execution.exceptions import ImplementationPlanError
from ai_enterprise.domain.execution.policies import (
    DEFAULT_FORBIDDEN_PATHS,
    ExecutionScope,
)

MAXIMUM_EDIT_BYTES = 200_000
MAXIMUM_TOTAL_EDITS = 50


@dataclass(frozen=True, slots=True)
class EditOperation:
    path: str
    mode: str
    content: str


@dataclass(frozen=True, slots=True)
class ImplementationPlan:
    edits: tuple[EditOperation, ...]
    raw_json: str


class ImplementationPlanner:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def plan(
        self,
        *,
        contract: dict[str, Any],
        tracked_files: list[str],
    ) -> ImplementationPlan:
        if self._settings.architecture_provider.strip().lower() == "scripted":
            raw_json = json.dumps({"edits": self._scripted_edits(contract)}, sort_keys=True)
            return ImplementationPlan(
                edits=self._parse_and_validate(raw_json, contract), raw_json=raw_json
            )
        llm = LLM(
            model=self._settings.ollama_model,
            base_url=self._settings.ollama_base_url,
            temperature=0.0,
            timeout=900,
            additional_params={
                "extra_body": {
                    "num_ctx": 16384,
                    "num_predict": 8192,
                },
            },
        )

        prompt = self._build_prompt(
            contract=contract,
            tracked_files=tracked_files,
        )

        try:
            raw = llm.call(
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ]
            )
        except Exception as exc:
            raise ImplementationPlanError(f"Implementation planner LLM call failed: {exc}") from exc

        raw_json = str(raw).strip()

        if not raw_json:
            raise ImplementationPlanError("Implementation planner returned an empty result")

        edits = self._parse_and_validate(raw_json, contract)

        return ImplementationPlan(edits=edits, raw_json=raw_json)

    @staticmethod
    def _scripted_edits(contract: dict[str, Any]) -> list[dict[str, str]]:
        title = str(contract.get("title", ""))
        if title != "Build bilingual menu storefront foundation":
            raise ImplementationPlanError(
                "Scripted implementation is not defined for this approved package"
            )
        return [
            {
                "path": "README.md",
                "mode": "create",
                "content": "# Like Mother's Home\n\nAccessible Romanian and English menu storefront foundation.\n\nRun `npm test` to verify localization, allergens, and semantic structure.\n",
            },
            {
                "path": "package.json",
                "mode": "create",
                "content": '{"name":"like-mothers-home","private":true,"type":"module","scripts":{"test":"node --test tests/menu.test.js"}}\n',
            },
            {
                "path": "src/index.html",
                "mode": "create",
                "content": """<!doctype html>
<html lang="ro"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Ca la Mama Acasă · Like Mother's Home</title><link rel="stylesheet" href="./styles.css"></head>
<body><a class="skip" href="#menu">Sari la meniu / Skip to menu</a>
<header><p class="eyebrow">Bucătărie românească autentică</p><h1>Ca la Mama Acasă</h1><p>Like Mother's Home · Romanian comfort food</p>
<button id="language" type="button" aria-label="Change language">RO / EN</button></header>
<nav aria-label="Categorii meniu / Menu categories"><div id="categories"></div></nav>
<main id="menu" tabindex="-1"><h2 id="menu-title">Meniul zilei</h2><div id="menu-grid" class="grid" aria-live="polite"></div></main>
<footer><p>Ingrediente românești · Romanian-sourced ingredients</p></footer><script type="module" src="./app.js"></script></body></html>
""",
            },
            {
                "path": "src/styles.css",
                "mode": "create",
                "content": """:root{color-scheme:light;--cream:#fff8e9;--ink:#30251d;--red:#9d2f2f;--green:#315d45}*{box-sizing:border-box}body{margin:0;background:var(--cream);color:var(--ink);font:1rem/1.6 system-ui,sans-serif}header,main,nav,footer{max-width:72rem;margin:auto;padding:1.25rem}header{padding-top:4rem}.eyebrow{color:var(--red);font-weight:700;text-transform:uppercase;letter-spacing:.08em}h1{font-family:Georgia,serif;font-size:clamp(2.5rem,8vw,5.5rem);line-height:1;margin:.2em 0}.skip{position:absolute;left:-9999px}.skip:focus{left:1rem;top:1rem;background:#fff;padding:.75rem;z-index:2}button{min-height:44px;border:2px solid var(--green);border-radius:999px;background:transparent;padding:.6rem 1rem;font-weight:700}button:focus-visible,a:focus-visible{outline:3px solid #e09b22;outline-offset:3px}#categories{display:flex;gap:.6rem;overflow:auto}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(16rem,1fr));gap:1rem}.dish{background:#fff;border:1px solid #e5d8c0;border-radius:1rem;padding:1.2rem;box-shadow:0 8px 24px #513b2010}.price{color:var(--green);font-weight:800}.allergens{font-size:.9rem;color:#654}@media(prefers-contrast:more){.dish{border:3px solid}button{background:#fff}}@media(max-width:36rem){header,main,nav,footer{padding:1rem}}""",
            },
            {
                "path": "src/app.js",
                "mode": "create",
                "content": """export const menu = {
  ro: { title: 'Meniul zilei', categories: ['Ciorbe', 'Gustări', 'Fel principal', 'Deserturi'],
    dishes: [{ name: 'Ciorbă de perișoare', description: 'Borș și legume românești',
      ingredients: ['carne de porc', 'orez', 'legume', 'borș'], allergens: ['ou', 'țelină'], price: 29 },
    { name: 'Sarmale cu mămăliguță', description: 'Rețetă tradițională cu smântână',
      ingredients: ['carne', 'varză murată', 'mălai'], allergens: ['lapte'], price: 42 }] },
  en: { title: "Today's menu", categories: ['Soups', 'Starters', 'Main courses', 'Desserts'],
    dishes: [{ name: 'Romanian meatball soup', description: 'Sour broth and Romanian vegetables',
      ingredients: ['pork', 'rice', 'vegetables', 'sour broth'], allergens: ['egg', 'celery'], price: 29 },
    { name: 'Cabbage rolls with polenta', description: 'Traditional recipe with sour cream',
      ingredients: ['meat', 'pickled cabbage', 'cornmeal'], allergens: ['milk'], price: 42 }] }
};
export function view(language = 'ro') { return menu[language] || menu.ro; }
function render(language) {
  const data = view(language); document.documentElement.lang = language;
  document.querySelector('#menu-title').textContent = data.title;
  document.querySelector('#categories').innerHTML = data.categories
    .map(x => `<button type="button">${x}</button>`).join('');
  document.querySelector('#menu-grid').innerHTML = data.dishes.map(d =>
    `<article class="dish"><h3>${d.name}</h3><p>${d.description}</p>` +
    `<p>${d.ingredients.join(' · ')}</p><p class="allergens"><strong>` +
    `${language === 'ro' ? 'Alergeni' : 'Allergens'}:</strong> ${d.allergens.join(', ')}</p>` +
    `<p class="price">${d.price} lei</p></article>`).join('');
}
if (typeof document !== 'undefined') {
  let language = 'ro'; document.querySelector('#language').addEventListener('click', () => {
    language = language === 'ro' ? 'en' : 'ro'; render(language);
  }); render(language);
}
""",
            },
            {
                "path": "tests/menu.test.js",
                "mode": "create",
                "content": """import test from 'node:test';
import assert from 'node:assert/strict';
import { menu, view } from '../src/app.js';
import { readFileSync } from 'node:fs';
test('offers Romanian and English menu data', () => {
  assert.equal(view('ro').categories[0], 'Ciorbe');
  assert.equal(view('en').categories[0], 'Soups');
  assert.equal(menu.ro.dishes.length, menu.en.dishes.length);
});
test('publishes ingredients, allergens and RON prices', () => {
  for (const language of ['ro', 'en']) for (const dish of menu[language].dishes) {
    assert.ok(dish.ingredients.length); assert.ok(dish.allergens.length); assert.ok(dish.price > 0);
  }
});
test('uses accessible semantic landmarks', () => {
  const html = readFileSync(new URL('../src/index.html', import.meta.url), 'utf8');
  for (const landmark of ['<header', '<nav', '<main', '<footer']) {
    assert.match(html, new RegExp(landmark));
  }
  assert.match(html, /class="skip"/);
  assert.match(html, /aria-live="polite"/);
});
""",
            },
        ]

    def _parse_and_validate(
        self,
        raw_json: str,
        contract: dict[str, Any],
    ) -> tuple[EditOperation, ...]:
        try:
            payload = json.loads(self._strip_code_fence(raw_json))
        except (json.JSONDecodeError, ValueError) as exc:
            raise ImplementationPlanError(
                f"Implementation planner returned invalid JSON: {exc}"
            ) from exc

        if isinstance(payload, dict) and "edits" in payload:
            raw_edits = payload["edits"]
        elif isinstance(payload, list):
            raw_edits = payload
        else:
            raise ImplementationPlanError(
                "Implementation planner result must be a JSON list of edits "
                "or an object with an 'edits' list"
            )

        if not isinstance(raw_edits, list) or not raw_edits:
            raise ImplementationPlanError("Implementation plan must contain at least one edit")

        if len(raw_edits) > MAXIMUM_TOTAL_EDITS:
            raise ImplementationPlanError(
                f"Implementation plan has too many edits: {len(raw_edits)}"
            )

        scope = self._build_scope(contract)

        allowed_files = set(contract["file_scope"]["allowed_files"])
        allowed_directories = set(contract["file_scope"].get("allowed_directories", []))

        edits: list[EditOperation] = []

        for raw_edit in raw_edits:
            path = self._clean_path(raw_edit)
            mode = raw_edit.get("mode", "create")
            content = raw_edit.get("content", "")

            if mode not in {"create", "overwrite", "append"}:
                raise ImplementationPlanError(f"Unsupported edit mode: {mode}")

            if not isinstance(content, str) or not content:
                raise ImplementationPlanError(f"Edit for {path} has empty content")

            if len(content.encode("utf-8")) > MAXIMUM_EDIT_BYTES:
                raise ImplementationPlanError(f"Edit for {path} exceeds content limit")

            if path not in allowed_files and not self._covered_by_directory(
                path,
                allowed_directories,
            ):
                raise ImplementationPlanError(f"Edit target outside approved scope: {path}")

            if not scope.is_allowed(path):
                raise ImplementationPlanError(f"Edit target is forbidden: {path}")

            edits.append(EditOperation(path=path, mode=mode, content=content))

        return tuple(edits)

    def _build_scope(self, contract: dict[str, Any]) -> ExecutionScope:
        allowed = list(contract["file_scope"]["allowed_files"])
        allowed.extend(contract["file_scope"].get("allowed_directories", []))

        forbidden = list(contract["file_scope"].get("forbidden_files", []))
        forbidden.extend(contract["file_scope"].get("forbidden_directories", []))
        forbidden.extend(DEFAULT_FORBIDDEN_PATHS)

        return ExecutionScope(
            allowed_paths=tuple(allowed),
            forbidden_paths=tuple(forbidden),
        )

    @staticmethod
    def _strip_code_fence(raw_json: str) -> str:
        text = raw_json.strip()

        if text.startswith("```"):
            lines = text.splitlines()

            if lines and lines[0].startswith("```"):
                lines = lines[1:]

            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]

            text = "\n".join(lines).strip()

        return text

    @staticmethod
    def _clean_path(raw_edit: Any) -> str:
        if not isinstance(raw_edit, dict):
            raise ImplementationPlanError("Implementation plan edits must be objects")

        raw_path = raw_edit.get("path")

        if not isinstance(raw_path, str) or not raw_path.strip():
            raise ImplementationPlanError("Implementation plan edit is missing a path")

        path = PurePosixPath(raw_path.strip())

        if path.is_absolute() or ".." in path.parts:
            raise ImplementationPlanError(f"Unsafe edit path: {raw_path}")

        return str(path)

    @staticmethod
    def _covered_by_directory(
        path: str,
        allowed_directories: set[str],
    ) -> bool:
        candidate = PurePosixPath(path)

        return any(
            PurePosixPath(directory) in candidate.parents for directory in allowed_directories
        )

    def _build_prompt(
        self,
        *,
        contract: dict[str, Any],
        tracked_files: list[str],
    ) -> str:
        file_scope = contract["file_scope"]
        command_policy = contract["command_policy"]

        required_changes = json.dumps(
            contract["required_changes"],
            indent=2,
        )

        return (
            "You are a software engineer implementing one bounded work "
            "package. Produce the exact file contents required to satisfy "
            "the work package using the /workspace repository.\n\n"
            "Work package title: {title}\n"
            "Objective: {objective}\n\n"
            "Required changes:\n{required_changes}\n\n"
            "Allowed file scope:\n{file_scope}\n\n"
            "Approved test commands (must pass):\n{test_commands}\n\n"
            "Existing tracked files in the repository:\n{tracked_files}\n\n"
            "Rules:\n"
            "- Return ONLY JSON of the form "
            '{{"edits": [{{"path": "...", "mode": "create|overwrite|append", '
            '"content": "..."}}]}}.\n'
            "- Every edit path must be inside the allowed file scope.\n"
            "- If the approved test command references a directory such as "
            "'tests', create passing tests inside that directory and ensure "
            "it is within the allowed scope.\n"
            "- Content must be complete, valid and ready to write; do not "
            "use placeholders.\n"
            "- Implement exactly the work package changes, nothing more."
        ).format(
            title=contract["title"],
            objective=contract["objective"],
            required_changes=required_changes,
            file_scope=json.dumps(file_scope, indent=2),
            test_commands=json.dumps(
                command_policy.get("test_commands", []),
                indent=2,
            ),
            tracked_files="\n".join(sorted(tracked_files)),
        )
