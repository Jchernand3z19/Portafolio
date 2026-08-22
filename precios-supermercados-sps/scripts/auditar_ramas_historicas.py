#!/usr/bin/env python3
"""Clasifica ramas históricas `precios-sps` contra `origin/main`.

La clasificación automática es deliberadamente conservadora:

* MERGED_OR_SUBSUMED: el tip es ancestro de main, el tree coincide o todos los
  commits no-merge tienen patch equivalente en main según `git cherry`.
* OPEN_CURRENT: todavía conserva cambios únicos y existe un PR abierto para el
  head exacto.
* UNIQUE_UNMERGED: conserva cambios únicos y no existe PR abierto. Estos son los
  únicos candidatos que requieren inspección humana para decidir si el trabajo
  sigue siendo útil o si corresponde reclasificarlo como CLOSED_SUPERSEDED.

El script no borra, fusiona ni modifica ramas. Usa sólo git local y, cuando se
proporciona GITHUB_TOKEN, la API pública de GitHub para el estado de PRs.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


CATEGORIES = {
    "MERGED_OR_SUBSUMED",
    "CLOSED_SUPERSEDED",
    "OPEN_CURRENT",
    "UNIQUE_UNMERGED",
}


class AuditError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class BranchAudit:
    branch: str
    category: str
    tip_sha: str
    unique_patch_count: int
    open_prs: tuple[int, ...]
    closed_unmerged_prs: tuple[int, ...]
    merged_prs: tuple[int, ...]
    reason: str


def _git(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", *args],
        check=False,
        capture_output=True,
        text=True,
    )
    if check and result.returncode != 0:
        raise AuditError(
            f"git {' '.join(args)} failed ({result.returncode}): {result.stderr.strip()}"
        )
    return result


def _ref_sha(ref: str) -> str:
    return _git("rev-parse", ref).stdout.strip()


def _is_ancestor(ancestor: str, descendant: str) -> bool:
    result = _git("merge-base", "--is-ancestor", ancestor, descendant, check=False)
    if result.returncode not in {0, 1}:
        raise AuditError(result.stderr.strip() or "merge-base failed")
    return result.returncode == 0


def _same_tree(left: str, right: str) -> bool:
    return _ref_sha(f"{left}^{{tree}}") == _ref_sha(f"{right}^{{tree}}")


def _unique_patches(main_ref: str, branch_ref: str) -> list[str]:
    result = _git("cherry", main_ref, branch_ref)
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return [line[2:] for line in lines if line.startswith("+ ")]


def _repository() -> tuple[str, str]:
    value = os.environ.get("GITHUB_REPOSITORY", "").strip()
    if "/" not in value:
        remote = _git("remote", "get-url", "origin").stdout.strip()
        suffix = remote.removesuffix(".git")
        if suffix.startswith("https://github.com/"):
            value = suffix.removeprefix("https://github.com/")
        elif suffix.startswith("git@github.com:"):
            value = suffix.removeprefix("git@github.com:")
    parts = value.split("/", maxsplit=1)
    if len(parts) != 2 or not all(parts):
        raise AuditError("cannot determine GitHub owner/repository")
    return parts[0], parts[1]


def _pull_requests_for_branch(branch: str) -> list[dict[str, Any]]:
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not token:
        return []
    owner, repo = _repository()
    query = urllib.parse.urlencode(
        {
            "state": "all",
            "head": f"{owner}:{branch}",
            "per_page": "100",
        }
    )
    request = urllib.request.Request(
        f"https://api.github.com/repos/{owner}/{repo}/pulls?{query}",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "precios-sps-branch-audit",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.load(response)
    except Exception as exc:  # pragma: no cover - sólo red real en workflow
        raise AuditError(f"GitHub PR lookup failed for {branch}: {type(exc).__name__}") from exc
    if not isinstance(payload, list):
        raise AuditError(f"GitHub PR lookup returned invalid payload for {branch}")
    return [item for item in payload if isinstance(item, dict)]


def _classify(main_ref: str, remote_prefix: str, branch: str) -> BranchAudit:
    ref = f"{remote_prefix}/{branch}"
    tip_sha = _ref_sha(ref)

    if _is_ancestor(ref, main_ref):
        return BranchAudit(
            branch=branch,
            category="MERGED_OR_SUBSUMED",
            tip_sha=tip_sha,
            unique_patch_count=0,
            open_prs=(),
            closed_unmerged_prs=(),
            merged_prs=(),
            reason="branch tip is an ancestor of main",
        )
    if _same_tree(ref, main_ref):
        return BranchAudit(
            branch=branch,
            category="MERGED_OR_SUBSUMED",
            tip_sha=tip_sha,
            unique_patch_count=0,
            open_prs=(),
            closed_unmerged_prs=(),
            merged_prs=(),
            reason="branch tree equals main tree",
        )

    unique_patches = _unique_patches(main_ref, ref)
    if not unique_patches:
        return BranchAudit(
            branch=branch,
            category="MERGED_OR_SUBSUMED",
            tip_sha=tip_sha,
            unique_patch_count=0,
            open_prs=(),
            closed_unmerged_prs=(),
            merged_prs=(),
            reason="all branch patches are patch-equivalent to main",
        )

    prs = _pull_requests_for_branch(branch)
    open_prs = tuple(
        sorted(int(pr["number"]) for pr in prs if pr.get("state") == "open")
    )
    merged_prs = tuple(
        sorted(int(pr["number"]) for pr in prs if pr.get("merged_at"))
    )
    closed_unmerged_prs = tuple(
        sorted(
            int(pr["number"])
            for pr in prs
            if pr.get("state") == "closed" and not pr.get("merged_at")
        )
    )
    category = "OPEN_CURRENT" if open_prs else "UNIQUE_UNMERGED"
    reason = (
        "unique patches remain and exact head has an open PR"
        if open_prs
        else "unique patches remain; requires manual intent/content inspection"
    )
    return BranchAudit(
        branch=branch,
        category=category,
        tip_sha=tip_sha,
        unique_patch_count=len(unique_patches),
        open_prs=open_prs,
        closed_unmerged_prs=closed_unmerged_prs,
        merged_prs=merged_prs,
        reason=reason,
    )


def _branches(remote_prefix: str, pattern: str) -> list[str]:
    raw = _git(
        "for-each-ref",
        "--format=%(refname:strip=3)",
        f"refs/remotes/{remote_prefix}/",
    ).stdout.splitlines()
    return sorted(
        branch.strip()
        for branch in raw
        if branch.strip() and branch.strip() != "HEAD" and pattern in branch
    )


def _markdown(rows: list[BranchAudit]) -> str:
    counts = {category: 0 for category in sorted(CATEGORIES)}
    for row in rows:
        counts[row.category] += 1
    lines = [
        "# Inventario preliminar de ramas precios-sps",
        "",
        f"Total: **{len(rows)}**",
        "",
    ]
    lines.extend(f"- {category}: **{counts[category]}**" for category in sorted(counts))
    candidates = [row for row in rows if row.category != "MERGED_OR_SUBSUMED"]
    lines.extend(["", "## Ramas que requieren atención", ""])
    if not candidates:
        lines.append("Ninguna.")
    else:
        lines.append("| rama | categoría | patches únicos | PR abiertos | PR cerrados sin merge |")
        lines.append("|---|---|---:|---|---|")
        for row in candidates:
            open_prs = ", ".join(f"#{number}" for number in row.open_prs) or "—"
            closed_prs = ", ".join(f"#{number}" for number in row.closed_unmerged_prs) or "—"
            lines.append(
                f"| `{row.branch}` | {row.category} | {row.unique_patch_count} | {open_prs} | {closed_prs} |"
            )
    lines.extend(
        [
            "",
            "> `UNIQUE_UNMERGED` es deliberadamente conservador: se inspecciona manualmente antes de decidir si es trabajo útil perdido o `CLOSED_SUPERSEDED`.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--main-ref", default="origin/main")
    parser.add_argument("--remote-prefix", default="origin")
    parser.add_argument("--pattern", default="precios-sps")
    parser.add_argument("--json-output", type=Path, default=Path("branch-audit.json"))
    parser.add_argument("--markdown-output", type=Path, default=Path("branch-audit.md"))
    args = parser.parse_args()

    _git("rev-parse", "--verify", args.main_ref)
    branches = _branches(args.remote_prefix, args.pattern)
    if not branches:
        raise AuditError(f"no remote branches matched {args.pattern!r}")

    rows = [
        _classify(args.main_ref, args.remote_prefix, branch)
        for branch in branches
    ]
    args.json_output.write_text(
        json.dumps([asdict(row) for row in rows], indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    markdown = _markdown(rows)
    args.markdown_output.write_text(markdown, encoding="utf-8")
    print(markdown)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AuditError as exc:
        print(f"branch_audit_error: {exc}", file=sys.stderr)
        raise SystemExit(2)
