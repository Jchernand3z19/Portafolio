from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = Path(__file__).with_name("validate_project_scope.py")
SPEC = importlib.util.spec_from_file_location("validate_project_scope", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)
REGISTRY = MODULE.load_registry(ROOT / ".github" / "project-scopes.yml")


class ProjectScopeTests(unittest.TestCase):
    def assert_pass(self, project_id: str, title: str, branch: str, files: list[str]) -> None:
        result = MODULE.validate_scope(REGISTRY, title=title, branch=branch, files=files)
        self.assertEqual(result.project_id, project_id)

    def assert_error(self, code: str, title: str, branch: str, files: list[str]) -> None:
        with self.assertRaises(MODULE.ScopeError) as raised:
            MODULE.validate_scope(REGISTRY, title=title, branch=branch, files=files)
        self.assertEqual(raised.exception.code, code)

    def test_project_only_changes_pass(self) -> None:
        self.assert_pass("rpi", "[RPI] Fix parser", "rpi/fix-parser", ["precios-supermercados-sps/src/parser.py"])
        self.assert_pass("pagos", "[PAGOS] Fix webhook", "pagos/fix-webhook", ["pagos-whatsapp-residencial/src/webhook.ts"])
        self.assert_pass("mundial", "[MUNDIAL] Tune model", "mundial/tune-model", ["mundial-2026/src/modelo_poisson.py"])

    def test_project_and_owned_workflow_pass(self) -> None:
        self.assert_pass(
            "rpi", "[RPI] Update analytics", "rpi/update-analytics",
            ["precios-supermercados-sps/src/a.py", ".github/workflows/precios-supermercados-sps-tests.yml"],
        )
        self.assert_pass(
            "pagos", "[PAGOS] Update CI", "pagos/update-ci",
            ["pagos-whatsapp-residencial/package.json", ".github/workflows/pagos-whatsapp-residencial-ci.yml"],
        )
        self.assert_pass(
            "rpi", "[RPI] Verify probe evidence", "rpi/verify-probe",
            [".github/workflows/requests/cloudflare-evidence-verify-request.json"],
        )

    def test_allowed_portfolio_integrations_pass(self) -> None:
        self.assert_pass(
            "rpi", "[RPI] Update portfolio", "rpi/update-portfolio",
            ["precios-supermercados-sps/portfolio/card.js", "js/main.js"],
        )
        self.assert_pass(
            "pagos", "[PAGOS] Add portfolio card", "pagos/add-card",
            ["pagos-whatsapp-residencial/portfolio/card.js", "index.html"],
        )

    def test_cross_project_change_fails(self) -> None:
        self.assert_error(
            "CROSS_PROJECT_CHANGE_NOT_ALLOWED", "[RPI] Mixed", "rpi/mixed",
            ["precios-supermercados-sps/README.md", "pagos-whatsapp-residencial/README.md"],
        )

    def test_wrong_workflow_and_prefixes_fail(self) -> None:
        self.assert_error(
            "CROSS_PROJECT_CHANGE_NOT_ALLOWED", "[RPI] Wrong workflow", "rpi/wrong-workflow",
            ["precios-supermercados-sps/README.md", ".github/workflows/mundial-2026-prediccion-viva.yml"],
        )
        self.assert_error(
            "PROJECT_TITLE_PREFIX_INVALID", "Update RPI", "rpi/update", ["precios-supermercados-sps/README.md"],
        )
        self.assert_error(
            "PROJECT_BRANCH_PREFIX_INVALID", "[RPI] Update", "feature/update", ["precios-supermercados-sps/README.md"],
        )

    def test_grandfathered_open_branches_pass(self) -> None:
        self.assert_pass(
            "rpi", "[RPI] Add controlled publication", "feat/rpi-controlled-publication-request",
            ["precios-supermercados-sps/.automation/rpi-publication-request.json"],
        )
        self.assert_pass(
            "pagos", "[PAGOS] Build MVP", "feat/pagos-whatsapp-residencial-mvp",
            ["pagos-whatsapp-residencial/package.json"],
        )

    def test_shared_governance_passes_but_is_not_a_bypass(self) -> None:
        self.assert_pass(
            "shared", "[MONOREPO] Enforce scopes", "monorepo/project-scopes",
            [
                "AGENTS.md", ".github/project-scopes.yml",
                ".github/workflows/precios-supermercados-sps-tests.yml",
                "precios-supermercados-sps/AGENTS.md", "mundial-2026/AGENTS.md",
            ],
        )
        self.assert_error(
            "CROSS_PROJECT_CHANGE_NOT_ALLOWED", "[MONOREPO] Mixed features", "monorepo/mixed",
            ["precios-supermercados-sps/src/a.py", "pagos-whatsapp-residencial/src/b.ts", "AGENTS.md"],
        )

    def test_project_cannot_hide_governance_or_unknown_paths(self) -> None:
        self.assert_error(
            "SHARED_SCOPE_INVALID", "[RPI] Change rules", "rpi/change-rules",
            ["precios-supermercados-sps/README.md", ".github/project-scopes.yml"],
        )
        self.assert_error(
            "PROJECT_SCOPE_UNRESOLVED", "[MONOREPO] Unknown", "monorepo/unknown",
            ["mystery-project/file.txt"],
        )

    def test_repository_workflow_registry_is_complete(self) -> None:
        MODULE.audit_repository(REGISTRY, ROOT)

    def test_scope_workflow_uses_current_trusted_base_without_pr_code(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "project-scope-check.yml").read_text()
        self.assertIn("pull_request_target:", workflow)
        self.assertIn("monorepo-project-scope-${{ github.event_name }}-", workflow)
        self.assertIn("name: tests", workflow)
        self.assertIn("ref: ${{ github.event.pull_request.base.ref }}", workflow)
        self.assertNotIn("ref: ${{ github.event.pull_request.base.sha }}", workflow)
        self.assertIn("persist-credentials: false", workflow)
        self.assertNotIn("secrets.", workflow)
        rpi_workflow = (ROOT / ".github" / "workflows" / "precios-supermercados-sps-tests.yml").read_text()
        self.assertIn("name: rpi-tests", rpi_workflow)


if __name__ == "__main__":
    unittest.main()
