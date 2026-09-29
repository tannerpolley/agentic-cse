from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "plugin/scripts/workflow/install_cse_hooks.py"

# Minimal stand-in for `codex app-server`: lists every hook in the repository's
# .codex/hooks.json plus one user-level hook, and keeps trust in FAKE_CODEX_STATE.
FAKE_CODEX = '''#!/usr/bin/env python3
import hashlib, json, os, sys
state = os.environ["FAKE_CODEX_STATE"]
trusted = json.load(open(state)) if os.path.exists(state) else {}
def entry(path, event, group, command):
    key = f"{path}:{event}:{group}:0"
    return {"key": key, "sourcePath": path, "command": command, "trustStatus":
            "trusted" if key in trusted else "untrusted", "currentHash": "sha256:" + hashlib.sha256(command.encode()).hexdigest()}
for line in sys.stdin:
    message = json.loads(line)
    if "id" not in message:
        continue
    params, result = message.get("params", {}), {}
    if message["method"] == "hooks/list":
        cwd = params["cwds"][0]
        path = os.path.join(cwd, ".codex/hooks.json")
        hooks = [entry("/user/hooks.json", "stop", 0, "user hook")]
        for event, groups in json.load(open(path))["hooks"].items():
            hooks += [entry(path, event.lower(), i, g["hooks"][0]["command"]) for i, g in enumerate(groups)]
        result = {"data": [{"cwd": cwd, "hooks": hooks}]}
    elif message["method"] == "config/value/write":
        assert params["keyPath"] == "hooks.state" and params["mergeStrategy"] == "upsert"
        trusted.update(params["value"])
        json.dump(trusted, open(state, "w"))
        with open(state + ".writes", "a") as log:
            log.write("write\\n")
    print(json.dumps({"jsonrpc": "2.0", "id": message["id"], "result": result}), flush=True)
'''


class CodexHookTrustTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.repo = self.root / "repo"
        (self.repo / "docs/scientific").mkdir(parents=True)
        (self.repo / "docs/scientific/CONTEXT.md").write_text("# Scientific context\n\nrepository role: analysis\n")
        (self.repo / ".codex").mkdir()
        (self.repo / ".codex/hooks.json").write_text(json.dumps(
            {"hooks": {"Stop": [{"hooks": [{"type": "command", "command": "other hook"}]}]}}))
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=self.repo, check=True)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        (self.bin / "git").symlink_to(shutil.which("git"))
        self.state = self.root / "trust.json"

    def install(self, *arguments: str):
        env = {**os.environ, "PATH": str(self.bin), "FAKE_CODEX_STATE": str(self.state)}
        return subprocess.run(
            [sys.executable, str(INSTALLER), "--home", str(self.root / "home"), "--repo", str(self.repo), *arguments],
            env=env, text=True, capture_output=True, check=False)

    def install_fake_codex(self):
        fake = self.bin / "codex"
        fake.write_text(FAKE_CODEX.replace("/usr/bin/env python3", sys.executable, 1))
        fake.chmod(0o755)

    def test_trusts_only_the_cse_hooks_and_diagnose_reports_them(self):
        self.install_fake_codex()
        result = self.install()
        self.assertEqual(0, result.returncode, result.stderr)
        registered = json.loads((self.repo / ".codex/hooks.json").read_text())["hooks"]
        path = str((self.repo / ".codex/hooks.json").resolve())
        expected = {
            f"{path}:{event.lower()}:{index}:0": {"trusted_hash": "sha256:" + hashlib.sha256(
                group["hooks"][0]["command"].encode()).hexdigest()}
            for event, groups in registered.items() for index, group in enumerate(groups)
            if "cse-test-gate.py" in group["hooks"][0]["command"]
        }
        self.assertEqual(4, len(expected))
        self.assertEqual(expected, json.loads(self.state.read_text()))

        self.assertEqual(0, self.install().returncode)
        self.assertEqual(1, len(Path(f"{self.state}.writes").read_text().splitlines()))
        report = json.loads(self.install("--diagnose").stdout)[0]["codex_hook_trust"]
        self.assertEqual("trusted", report["status"])
        self.assertEqual(4, len(report["hooks"]))

    def test_missing_codex_keeps_registration_and_warns_hooks_will_be_skipped(self):
        result = self.install()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("cse-test-gate.py", (self.repo / ".codex/hooks.json").read_text())
        self.assertIn("will skip these hooks", result.stderr)
        report = json.loads(self.install("--diagnose").stdout)[0]["codex_hook_trust"]
        self.assertEqual("unknown", report["status"])


if __name__ == "__main__":
    unittest.main()
