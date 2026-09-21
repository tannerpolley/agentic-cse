from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "plugin/scripts/workflow/setup_scientific_project.py"
BEGIN = "<!-- CSE:BEGIN PROTOCOL -->"
END = "<!-- CSE:END PROTOCOL -->"
ROLE = "chemical engineer and computational thermodynamics researcher"
DUTIES = "Own the ePC-SAFT parameter decisions and their numerical evidence."
LEGACY_POINTER = "Use the installed CSE skills and read docs/scientific/README.md before route selection."


def run(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(SCRIPT), *args], cwd=cwd, text=True, capture_output=True, check=False)


class ManagedProtocolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name).resolve()

    def agents(self) -> str:
        return (self.repo / "AGENTS.md").read_text(encoding="utf-8")

    def context(self) -> str:
        return (self.repo / "docs/scientific/CONTEXT.md").read_text(encoding="utf-8")

    def block(self, text: str) -> str:
        self.assertEqual(text.count(BEGIN), 1)
        self.assertEqual(text.count(END), 1)
        return text[text.index(BEGIN):text.index(END) + len(END)]

    def check(self) -> subprocess.CompletedProcess[str]:
        return run("--repo", str(self.repo), "--check-routing", cwd=self.repo)

    def approve(self, *extra: str) -> subprocess.CompletedProcess[str]:
        return run("--repo", str(self.repo), "--reconcile", "--approve", "--role", "analysis", *extra, cwd=self.repo)

    def prepare(self, *extra: str) -> subprocess.CompletedProcess[str]:
        (self.repo / "data").mkdir(exist_ok=True)
        (self.repo / "data/observations.csv").write_text("t_s,T_degC\n0,90\n", encoding="utf-8")
        return run("--repo", str(self.repo), "--role", "tool", "--analysis-id", "cooling-fit",
                   "--input", "data/observations.csv", "--manifest", str(self.repo / ".cse/manifest.json"),
                   *extra, cwd=self.repo)

    def legacy_repository(self) -> None:
        (self.repo / "AGENTS.md").write_text(
            f"# My project\n\nKeep the custom build notes.\n\n{LEGACY_POINTER}\n\nCSE execution mode: baton.\n",
            encoding="utf-8",
        )
        scientific = self.repo / "docs/scientific"
        scientific.mkdir(parents=True)
        (scientific / "README.md").write_text("# Scientific project records\n", encoding="utf-8")
        (scientific / "CONTEXT.md").write_text(
            "# Scientific context\n\nrepository role: analysis\n\n## Question and intended use\n\nCooling rate.\n",
            encoding="utf-8",
        )

    def test_fresh_setup_writes_role_first_block_and_repeats_byte_for_byte(self):
        missing = self.prepare()
        self.assertEqual(missing.returncode, 1)
        self.assertIn("agent role is required", missing.stderr)
        self.assertFalse((self.repo / "AGENTS.md").exists())

        result = self.prepare("--agent-role", ROLE, "--responsibilities", DUTIES)
        self.assertEqual(result.returncode, 0, result.stderr)
        text = self.agents()
        block = self.block(text)
        lines = [line for line in block.splitlines()[1:-1] if line.strip()]
        self.assertEqual(lines[0], "## CSE Protocol")
        self.assertEqual(lines[1], f"**Agent role:** Work as {ROLE}.")
        self.assertEqual(lines[2], "**Repository role:** tool.")
        self.assertIn(DUTIES, block)
        self.assertTrue(text.startswith("# CSE project guidance\n\n" + BEGIN), text[:120])
        self.assertNotIn("MUST use the installed CSE skills", text)
        self.assertIn("CSE execution mode: direct.", text)
        self.assertIn(f"## Agent role\n\nagent role: {ROLE}\n\n{DUTIES}\n", self.context())
        self.assertIn("repository role: tool", self.context())
        self.assertEqual(self.check().returncode, 0)

        before = (text, self.context())
        again = self.prepare()
        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertEqual((self.agents(), self.context()), before)

    def test_pointer_only_repository_is_diagnosed_then_upgraded_preserving_guidance(self):
        self.legacy_repository()
        check = self.check()
        self.assertEqual(check.returncode, 1)
        self.assertIn("Managed CSE Protocol block: missing; agent role: missing", check.stdout)

        refused = self.approve()
        self.assertEqual(refused.returncode, 1)
        self.assertIn("agent role is required", refused.stderr)
        self.assertIn(LEGACY_POINTER, self.agents())

        applied = self.approve("--agent-role", ROLE)
        self.assertEqual(applied.returncode, 0, applied.stderr)
        text = self.agents()
        block = self.block(text)
        self.assertTrue(text.startswith("# My project\n\n" + BEGIN), text[:120])
        self.assertIn("Keep the custom build notes.", text)
        self.assertIn("CSE execution mode: baton.", text)
        self.assertNotIn(LEGACY_POINTER, text)
        self.assertIn("**Repository role:** analysis.", block)
        self.assertIn(f"agent role: {ROLE}", self.context())
        self.assertIn("Cooling rate.", self.context())
        self.assertEqual(self.check().returncode, 0)

        before = (text, self.context())
        again = self.approve()
        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertEqual((self.agents(), self.context()), before)

    def test_role_change_manual_drift_and_malformed_markers(self):
        self.legacy_repository()
        self.assertEqual(self.approve("--agent-role", ROLE).returncode, 0)

        changed = self.approve("--agent-role", "heat-transfer modeling researcher",
                               "--responsibilities", "Own the cooling model.")
        self.assertEqual(changed.returncode, 0, changed.stderr)
        text = self.agents()
        self.assertIn("**Agent role:** Work as heat-transfer modeling researcher.", text)
        self.assertNotIn(ROLE, text)
        self.assertNotIn(ROLE, self.context())
        self.assertIn("Own the cooling model.", self.context())
        self.assertIn("Own the cooling model.", self.block(text))

        (self.repo / "AGENTS.md").write_text(text.replace("Work as heat-transfer", "Work as a manually edited"), encoding="utf-8")
        drift = self.check()
        self.assertEqual(drift.returncode, 1)
        self.assertIn("Managed CSE Protocol block: stale", drift.stdout)
        self.assertIn("-**Agent role:** Work as a manually edited", drift.stdout)
        self.assertIn("+**Agent role:** Work as heat-transfer", drift.stdout)
        repaired = self.approve()
        self.assertEqual(repaired.returncode, 0, repaired.stderr)
        self.assertEqual(self.agents(), text)

        broken = text + "\n" + BEGIN + "\n"
        (self.repo / "AGENTS.md").write_text(broken, encoding="utf-8")
        self.assertIn("malformed", self.check().stdout)
        refused = self.approve()
        self.assertEqual(refused.returncode, 1)
        self.assertIn("unmatched", refused.stderr)
        self.assertEqual(self.agents(), broken)


if __name__ == "__main__":
    unittest.main()
