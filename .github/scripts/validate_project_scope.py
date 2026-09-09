#!/usr/bin/env python3
"""Validate pull-request ownership from the monorepo scope registry and paths."""
from __future__ import annotations

import argparse
import fnmatch
import json
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Iterable


class ScopeError(ValueError):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class ScopeResult:
    project_id: str
    project_root: str
    shared_integrations: tuple[str, ...]
    changed_file_count: int


def load_registry(path: Path) -> dict:
    """The registry is JSON syntax, which is valid YAML 1.2, so stdlib is enough."""
    try:
        registry = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ScopeError("PROJECT_REGISTRY_INVALID", str(exc)) from exc
    if not isinstance(registry, dict) or registry.get("schema") != "portfolio-project-scopes/v1":
        raise ScopeError("PROJECT_REGISTRY_INVALID", "schema must be portfolio-project-scopes/v1")
    projects = registry.get("projects")
    shared = registry.get("shared")
    policy = registry.get("policy")
    if not isinstance(projects, dict) or not projects or not isinstance(shared, dict) or not isinstance(policy, dict):
        raise ScopeError("PROJECT_REGISTRY_INVALID", "projects, shared and policy are required")

    roots: set[str] = set()
    title_prefixes: set[str] = set()
    branch_prefixes: set[str] = set()
    workflows: dict[str, str] = {}
    for project_id, project in projects.items():
        if not isinstance(project_id, str) or not isinstance(project, dict):
            raise ScopeError("PROJECT_REGISTRY_INVALID", "project entry is invalid")
        root = project.get("root")
        title = project.get("title_prefix")
        branch = project.get("branch_prefix")
        if not all(isinstance(value, str) and value for value in (root, title, branch)):
            raise ScopeError("PROJECT_REGISTRY_INVALID", f"{project_id} has incomplete identity")
        if root in roots or title in title_prefixes or branch in branch_prefixes:
            raise ScopeError("PROJECT_REGISTRY_INVALID", f"{project_id} duplicates a project identity")
        roots.add(root)
        title_prefixes.add(title)
        branch_prefixes.add(branch)
        for workflow in project.get("owned_workflows", []):
            if workflow in workflows:
                raise ScopeError(
                    "PROJECT_REGISTRY_INVALID",
                    f"workflow {workflow} belongs to both {workflows[workflow]} and {project_id}",
                )
            workflows[workflow] = project_id
    return registry


def _clean_files(files: Iterable[str]) -> tuple[str, ...]:
    clean: list[str] = []
    for raw in files:
        if not isinstance(raw, str):
            raise ScopeError("PROJECT_SCOPE_UNRESOLVED", "changed file path is not text")
        value = raw.strip().replace("\\", "/")
        path = PurePosixPath(value)
        if not value or path.is_absolute() or ".." in path.parts:
            raise ScopeError("PROJECT_SCOPE_UNRESOLVED", f"invalid changed path: {raw!r}")
        clean.append(value)
    if not clean:
        raise ScopeError("PROJECT_SCOPE_UNRESOLVED", "pull request has no changed files")
    if len(set(clean)) != len(clean):
        raise ScopeError("PROJECT_SCOPE_AMBIGUOUS", "changed file list contains duplicates")
    return tuple(sorted(clean))


def _matches(path: str, patterns: Iterable[str]) -> bool:
    return any(fnmatch.fnmatchcase(path, pattern) for pattern in patterns)


def _declared_project(registry: dict, title: str) -> str | None:
    matches = [
        project_id
        for project_id, project in registry["projects"].items()
        if title.startswith(project["title_prefix"] + " ")
    ]
    shared_id = registry["policy"]["shared_project_id"]
    if title.startswith(registry["policy"]["shared_title_prefix"] + " "):
        matches.append(shared_id)
    if len(matches) > 1:
        raise ScopeError("PROJECT_SCOPE_AMBIGUOUS", "title declares more than one project")
    return matches[0] if matches else None


def validate_scope(registry: dict, *, title: str, branch: str, files: Iterable[str]) -> ScopeResult:
    changed = _clean_files(files)
    projects = registry["projects"]
    shared = registry["shared"]
    project_files: dict[str, list[str]] = {project_id: [] for project_id in projects}
    governance_files: list[str] = []
    integration_files: dict[str, list[str]] = {
        name: [] for name in shared.get("integrations", {})
    }
    unresolved: list[str] = []

    for path in changed:
        owners = []
        for project_id, project in projects.items():
            patterns = tuple(project.get("owned_paths", ())) + tuple(project.get("owned_workflows", ()))
            if _matches(path, patterns):
                owners.append(project_id)
        governance = _matches(path, shared.get("governance_paths", ()))
        integrations = [
            name
            for name, integration in shared.get("integrations", {}).items()
            if _matches(path, integration.get("paths", ()))
        ]
        if governance:
            owners = []
        if len(owners) > 1 or (owners and integrations) or (governance and integrations):
            raise ScopeError("PROJECT_SCOPE_AMBIGUOUS", f"path has overlapping ownership: {path}")
        if owners:
            project_files[owners[0]].append(path)
        elif governance:
            governance_files.append(path)
        elif len(integrations) == 1:
            integration_files[integrations[0]].append(path)
        elif len(integrations) > 1:
            raise ScopeError("PROJECT_SCOPE_AMBIGUOUS", f"path matches multiple integrations: {path}")
        else:
            unresolved.append(path)

    if unresolved:
        raise ScopeError("PROJECT_SCOPE_UNRESOLVED", ", ".join(unresolved))
    declared = _declared_project(registry, title)
    shared_id = registry["policy"]["shared_project_id"]
    detected = [project_id for project_id, paths in project_files.items() if paths]
    shared_workflow_migration = (
        declared == shared_id
        and ".github/project-scopes.yml" in governance_files
        and all(
            path in projects[project_id].get("owned_workflows", ())
            for project_id in detected
            for path in project_files[project_id]
        )
    )
    if shared_workflow_migration:
        detected = []
    if len(detected) > 1:
        detail = ", ".join(f"{project_id}={project_files[project_id][0]}" for project_id in detected)
        raise ScopeError("CROSS_PROJECT_CHANGE_NOT_ALLOWED", detail)

    active_integrations = tuple(sorted(name for name, paths in integration_files.items() if paths))
    if detected:
        project_id = detected[0]
        if declared != project_id:
            raise ScopeError(
                "PROJECT_TITLE_PREFIX_INVALID",
                f"expected {projects[project_id]['title_prefix']} for {project_id}",
            )
        if governance_files:
            raise ScopeError(
                "SHARED_SCOPE_INVALID",
                "project PR includes governance paths: " + ", ".join(governance_files),
            )
        for name in active_integrations:
            allowed = shared["integrations"][name].get("allowed_projects", ())
            if project_id not in allowed:
                raise ScopeError("SHARED_SCOPE_INVALID", f"{name} is not allowed for {project_id}")
        expected_branch = projects[project_id]["branch_prefix"]
        grandfathered = registry["policy"].get("grandfathered_branches", {})
        if not branch.startswith(expected_branch) and grandfathered.get(branch) != project_id:
            raise ScopeError(
                "PROJECT_BRANCH_PREFIX_INVALID",
                f"expected {expected_branch} for {project_id}; got {branch}",
            )
        return ScopeResult(project_id, projects[project_id]["root"], active_integrations, len(changed))

    if declared != shared_id:
        raise ScopeError(
            "PROJECT_SCOPE_UNRESOLVED",
            "shared-only changes require the [MONOREPO] title prefix",
        )
    expected_branch = registry["policy"]["shared_branch_prefix"]
    if not branch.startswith(expected_branch):
        raise ScopeError(
            "PROJECT_BRANCH_PREFIX_INVALID",
            f"expected {expected_branch} for shared governance; got {branch}",
        )
    return ScopeResult(shared_id, "/", active_integrations, len(changed))


def audit_repository(registry: dict, repository: Path) -> None:
    registered_workflows = {
        path
        for project in registry["projects"].values()
        for path in project.get("owned_workflows", ())
    }
    registered_workflows.update(
        path
        for integration in registry["shared"].get("integrations", {}).values()
        for path in integration.get("paths", ())
        if path.startswith(".github/workflows/") and "*" not in path
    )
    registered_workflows.add(".github/workflows/project-scope-check.yml")
    actual = {
        str(path.relative_to(repository))
        for path in (repository / ".github" / "workflows").glob("*.yml")
    }
    missing = sorted(actual - registered_workflows)
    phantom = sorted(path for path in registered_workflows - actual if "pagos-whatsapp" not in path)
    if missing or phantom:
        raise ScopeError(
            "PROJECT_REGISTRY_INVALID",
            f"unregistered_workflows={missing}; missing_workflows={phantom}",
        )


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--config", type=Path, required=True)
    result.add_argument("--title")
    result.add_argument("--branch")
    result.add_argument("--files-file", type=Path)
    result.add_argument("--audit-repository", type=Path)
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        registry = load_registry(args.config)
        if args.audit_repository is not None:
            audit_repository(registry, args.audit_repository)
            print(json.dumps({"status": "ok", "audit": "repository"}, sort_keys=True))
            return 0
        if args.title is None or args.branch is None or args.files_file is None:
            raise ScopeError("PROJECT_SCOPE_UNRESOLVED", "title, branch and files-file are required")
        files = args.files_file.read_text(encoding="utf-8").splitlines()
        result = validate_scope(registry, title=args.title, branch=args.branch, files=files)
    except (OSError, ScopeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps({
        "status": "ok",
        "project_id": result.project_id,
        "project_root": result.project_root,
        "shared_integrations": result.shared_integrations,
        "changed_file_count": result.changed_file_count,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
