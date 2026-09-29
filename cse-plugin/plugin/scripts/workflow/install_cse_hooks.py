#!/usr/bin/env python3
"""Install the stable CSE hook runtime and opt CSE repositories into it."""

from __future__ import annotations

import argparse
import hashlib
import json
import itertools
import os
from pathlib import Path
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import tomllib

from cse_hook_common import nearest_context
from setup_scientific_project import routing_report


ROOT = Path(__file__).resolve().parents[2]
RUNTIME_SOURCE = ROOT / "scripts/workflow/cse-test-gate.py"
COMMON_SOURCE = ROOT / "scripts/workflow/cse_hook_common.py"
PROSE_SOURCE = ROOT / "scripts/workflow/check_prose.py"
STANCE_SOURCE = ROOT / "assets/workflow/scientific-stance.txt"
ROUTING_SOURCE = ROOT / "assets/workflow/skill-routing.txt"
CONFIG_SOURCE = ROOT / "assets/workflow/codex/hooks.json"
EVENTS = {"SessionStart", "SubagentStart", "UserPromptSubmit", "Stop"}
FORBIDDEN = ("plugins/cache", "PLUGIN_ROOT", "CLAUDE_PLUGIN_ROOT")
RUNTIME_DIRECTORY = Path(".local/share/cse/hooks")
CODEX_TIMEOUT = 30
NO_HOOKS_LISTED = "Codex lists no CSE hooks for this repository (project not trusted in Codex, or hooks disabled)"
SKIPPED_UNTRUSTED = "Codex will skip these hooks until they are trusted (run /hooks in the Codex TUI)"
CONFIG_PATHS = {"codex": Path(".codex/hooks.json"), "claude": Path(".claude/settings.json")}
# The same relative paths hold the user-level registration under $HOME (--user).


class InstallError(RuntimeError):
    pass


def validate_sources() -> None:
    compile(RUNTIME_SOURCE.read_text(encoding="utf-8"), str(RUNTIME_SOURCE), "exec")
    compile(COMMON_SOURCE.read_text(encoding="utf-8"), str(COMMON_SOURCE), "exec")
    compile(PROSE_SOURCE.read_text(encoding="utf-8"), str(PROSE_SOURCE), "exec")
    stance = STANCE_SOURCE.read_text(encoding="utf-8").strip()
    if not stance or len(stance.split()) > 180:
        raise InstallError("scientific stance must contain 1 to 180 words")
    if not ROUTING_SOURCE.read_text(encoding="utf-8").strip():
        raise InstallError("skill routing text must not be empty")
    config_text = CONFIG_SOURCE.read_text(encoding="utf-8")
    config = json.loads(config_text)
    hooks = config.get("hooks") if isinstance(config, dict) else None
    if not isinstance(hooks, dict) or set(hooks) != EVENTS:
        raise InstallError("project hook configuration does not define the four CSE events")
    for event, groups in hooks.items():
        if not isinstance(groups, list) or not groups:
            raise InstallError(f"invalid project hook configuration: {event}")
        for group in groups:
            if not isinstance(group, dict) or not isinstance(group.get("hooks"), list):
                raise InstallError(f"invalid project hook group: {event}")
            for handler in group["hooks"]:
                if not isinstance(handler, dict) or handler.get("type") != "command" or not isinstance(handler.get("command"), str):
                    raise InstallError(f"invalid project hook handler: {event}")
    if any(term in config_text for term in FORBIDDEN):
        raise InstallError("project hook configuration depends on a plugin or cache path")
    if (ROOT / "hooks/hooks.json").exists():
        raise InstallError("plugin-bundled hooks must remain absent")


def check_target(target: Path) -> None:
    if any(path.is_symlink() for path in (target, *target.parents)):
        raise InstallError(f"refusing symlink hook target: {target}")
    if target.exists() and not target.is_file():
        raise InstallError(f"hook target is not a file: {target}")


def atomic_write(target: Path, content: bytes, mode: int) -> None:
    check_target(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.chmod(mode)
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def runtime_files(home: Path):
    directory = home.resolve() / RUNTIME_DIRECTORY
    return (
        (RUNTIME_SOURCE, directory / "cse-test-gate.py", 0o755),
        (COMMON_SOURCE, directory / "cse_hook_common.py", 0o644),
        (PROSE_SOURCE, directory / "check_prose.py", 0o644),
        (ROOT / "BANNED.md", directory / "cse-BANNED.md", 0o644),
        (STANCE_SOURCE, directory / "cse-scientific-stance.txt", 0o644),
        (ROUTING_SOURCE, directory / "cse-skill-routing.txt", 0o644),
    )


def install_runtime(home: Path, replace: bool) -> list[tuple[Path, str]]:
    files = runtime_files(home)
    # Check every target before replacing any shared runtime file.
    for source, target, _ in files:
        check_target(target)
        if target.exists() and target.read_bytes() != source.read_bytes() and not replace:
            raise InstallError(f"stable hook differs: {target}; use --replace-runtime for a deliberate hook update")
    results = []
    for source, target, mode in files:
        content = source.read_bytes()
        if target.is_file() and target.read_bytes() == content:
            results.append((target, "unchanged"))
            continue
        atomic_write(target, content, mode)
        results.append((target, "installed"))
    return results


def project_root(path: Path) -> Path:
    path = path.resolve()
    result = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "--show-toplevel"],
        capture_output=True, text=True, check=False, timeout=5,
    )
    if result.returncode:
        raise InstallError(f"not a Git repository: {path}")
    repository = Path(result.stdout.strip()).resolve()
    found = nearest_context(path, repository)
    if found is None:
        raise InstallError(f"no CSE context at or above: {path}")
    return found.parents[2]


def configuration(agent: str) -> dict:
    config = json.loads(CONFIG_SOURCE.read_text(encoding="utf-8"))
    return {"hooks": config["hooks"]} if agent == "claude" else config


def owned_commands(event: str) -> dict[str, Path]:
    """Current guarded command plus earlier unguarded forms, so reinstalls replace them."""
    owned = {}
    for directory in (".codex/hooks", str(RUNTIME_DIRECTORY)):
        script = f'"$HOME/{directory}/cse-test-gate.py"'
        relative = Path(directory) / "cse-test-gate.py"
        for python in ("python3", "/usr/bin/python3"):
            owned[f"{python} {script} {event}"] = relative
        owned[f"[ ! -f {script} ] || python3 {script} {event}"] = relative
    return owned


def merged_configuration(target: Path, agent: str, add: bool = True) -> dict:
    """The target's configuration with recognized CSE handlers replaced (add) or removed."""
    check_target(target)
    result = json.loads(target.read_text()) if target.exists() else {}
    if not isinstance(result, dict) or not isinstance(result.get("hooks", {}), dict):
        raise InstallError(f"invalid hook configuration: {target}")
    hooks = result.setdefault("hooks", {})
    for event, groups in list(hooks.items()):
        if not isinstance(groups, list):
            raise InstallError(f"invalid hook event: {event}")
        retained = []
        for group in groups:
            if not isinstance(group, dict) or not isinstance(group.get("hooks"), list):
                raise InstallError(f"invalid hook group: {event}")
            owned = owned_commands(event)
            handlers = [h for h in group["hooks"] if not (
                isinstance(h, dict) and h.get("type") == "command" and h.get("command") in owned)]
            if handlers:
                retained.append({**group, "hooks": handlers})
        if retained:
            hooks[event] = retained
        else:
            del hooks[event]
    if not add:
        return result
    desired = configuration(agent)
    for event, groups in desired["hooks"].items():
        hooks.setdefault(event, []).extend(groups)
    if agent == "codex":
        result.setdefault("description", desired["description"])
    return result


def write_registration(target: Path, agent: str, add: bool) -> tuple[Path, str]:
    content = (json.dumps(merged_configuration(target, agent, add), indent=2) + "\n").encode()
    if target.is_file() and target.read_bytes() == content or not add and not target.exists():
        return target, "unchanged"
    atomic_write(target, content, 0o644)
    return target, "installed" if add else "removed"


def install_repository(path: Path, agent: str = "codex", add: bool = True) -> tuple[Path, str]:
    return write_registration(project_root(path) / CONFIG_PATHS[agent], agent, add)


def codex_cse_hooks(root: Path, trust: bool, source: Path | None = None) -> tuple[list[dict], list[str]]:
    """List the CSE hooks Codex reads from the repository's .codex/hooks.json.

    With trust=True, persist trust for the ones not yet trusted and return the refreshed
    list plus the keys newly trusted. Talks to `codex app-server` (JSON-RPC over stdio).
    """
    # CSE_CODEX_BIN selects the Codex CLI (as in sync-live.sh); trust lands in that CLI's CODEX_HOME.
    codex = shutil.which(os.environ.get("CSE_CODEX_BIN", "codex"))
    if codex is None:
        raise InstallError("codex CLI not found")
    target = (source or root / CONFIG_PATHS["codex"]).resolve()
    owned = {command for event in EVENTS for command in owned_commands(event)}
    deadline = time.monotonic() + CODEX_TIMEOUT
    try:
        proc = subprocess.Popen([codex, "app-server"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL, text=True)
    except OSError as exc:
        raise InstallError(f"codex app-server could not start: {exc}") from exc
    lines: queue.Queue = queue.Queue()
    threading.Thread(target=lambda: ([lines.put(line) for line in proc.stdout], lines.put(None)),
                     daemon=True).start()
    identifiers = itertools.count(1)

    def send(message: dict) -> None:
        proc.stdin.write(json.dumps({"jsonrpc": "2.0", **message}) + "\n")
        proc.stdin.flush()

    def call(method: str, params: dict) -> dict:
        identifier = next(identifiers)
        send({"id": identifier, "method": method, "params": params})
        while True:
            try:
                line = lines.get(timeout=max(deadline - time.monotonic(), 0))
            except queue.Empty:
                raise InstallError(f"codex app-server timed out after {CODEX_TIMEOUT} s") from None
            if line is None:
                raise InstallError("codex app-server exited early")
            try:
                reply = json.loads(line)
            except ValueError:
                continue
            if reply.get("id") == identifier:
                if "error" in reply:
                    raise InstallError(f"codex app-server rejected {method}: {reply['error']}")
                return reply["result"]

    def listing() -> list[dict]:
        hooks = call("hooks/list", {"cwds": [str(root)]})["data"][0]["hooks"]
        return [h for h in hooks if Path(h["sourcePath"]).resolve() == target and h["command"] in owned]

    try:
        call("initialize", {"clientInfo": {"name": "cse-hooks", "version": "0"}})
        send({"method": "initialized"})
        hooks = listing()
        pending = [h for h in hooks if h["trustStatus"] != "trusted"]
        if trust and pending:
            call("config/value/write", {
                "keyPath": "hooks.state", "mergeStrategy": "upsert", "filePath": None, "expectedVersion": None,
                "value": {h["key"]: {"trusted_hash": h["currentHash"]} for h in pending}})
            hooks = listing()
        return hooks, [h["key"] for h in pending] if trust else []
    except (OSError, KeyError, IndexError, TypeError) as exc:
        raise InstallError(f"unexpected codex app-server exchange: {exc!r}") from exc
    finally:
        proc.kill()
        proc.wait()


def codex_trust_report(root: Path) -> dict:
    """Read-only trust status of the CSE hooks: trusted, untrusted, or unknown."""
    if not (root / CONFIG_PATHS["codex"]).is_file():
        return {"status": "unknown", "reason": "no repository hook registration"}
    try:
        hooks, _ = codex_cse_hooks(root, trust=False)
    except InstallError as exc:
        return {"status": "unknown", "reason": str(exc)}
    if not hooks:
        return {"status": "unknown", "reason": NO_HOOKS_LISTED}
    status = "trusted" if all(h["trustStatus"] == "trusted" for h in hooks) else "untrusted"
    return {"status": status, "hooks": {h["key"]: h["trustStatus"] for h in hooks}}


def diagnose_configuration(target: Path, home: Path) -> dict:
    report = {"path": str(target), "exists": None, "registrations": [], "saved_cse_state": {}}
    try:
        check_target(target)
        report["exists"] = target.is_file()
        if not report["exists"]:
            return report
        text = target.read_text()
        data = tomllib.loads(text) if target.suffix == ".toml" else json.loads(text)
        hooks = data.get("hooks", {})
        if not isinstance(hooks, dict):
            raise ValueError("hooks must be an object")
        for key, state in hooks.get("state", {}).items():
            if key.startswith("cse@") and isinstance(state, dict):
                report["saved_cse_state"][key] = {"enabled": state.get("enabled")}
        for event, groups in hooks.items():
            if event == "state":
                continue
            if not isinstance(groups, list):
                raise ValueError(f"invalid hook event: {event}")
            for group in groups:
                if not isinstance(group, dict) or not isinstance(group.get("hooks"), list):
                    raise ValueError(f"invalid hook group: {event}")
                for handler in group["hooks"]:
                    if not isinstance(handler, dict):
                        raise ValueError(f"invalid hook handler: {event}")
                    command = handler.get("command", "")
                    if not isinstance(command, str):
                        raise ValueError(f"invalid hook command: {event}")
                    if handler.get("type") != "command" or "cse-test-gate.py" not in command:
                        continue
                    relative = owned_commands(event).get(command)
                    entry = {"event": event, "command": command, "target": None,
                             "target_exists": None, "recognized": relative is not None}
                    if relative is not None:
                        installed = home / relative
                        entry["target"] = str(installed)
                        entry["legacy"] = relative.parent != RUNTIME_DIRECTORY
                        try:
                            check_target(installed)
                            entry["target_exists"] = installed.is_file()
                        except InstallError as exc:
                            entry["error"] = str(exc)
                    report["registrations"].append(entry)
    except (InstallError, OSError, ValueError, AttributeError, TypeError) as exc:
        report["error"] = str(exc)
    return report


def diagnose(path: Path, home: Path, agent: str) -> dict:
    root = project_root(path)
    home = home.resolve()
    routing = routing_report(root)
    target = root / CONFIG_PATHS[agent]
    runtime = []
    for source, installed, _ in runtime_files(home):
        try:
            check_target(installed)
        except InstallError as exc:
            runtime.append({"path": str(installed), "matches_source": False,
                            "sha256": None, "error": str(exc)})
            continue
        runtime.append({"path": str(installed), "matches_source": installed.is_file()
                        and installed.read_bytes() == source.read_bytes(),
                        "sha256": hashlib.sha256(installed.read_bytes()).hexdigest() if installed.is_file() else None})
    paths = ([home / ".codex/hooks.json", home / ".codex/config.toml",
              root / ".codex/hooks.json", root / ".codex/config.toml"] if agent == "codex" else
             [home / ".claude/settings.json", root / ".claude/settings.json", root / ".claude/settings.local.json"])
    sources = [diagnose_configuration(source, home) for source in paths]
    selected = next(source for source in sources if source["path"] == str(target))
    current = False
    if selected.get("exists") and "error" not in selected:
        try:
            current = json.loads(target.read_text()) == merged_configuration(target, agent)
        except (InstallError, OSError, ValueError) as exc:
            selected["error"] = str(exc)
    fresh_session_check = {
        "codex": "Fresh Codex check: open a new session in this repository, run /hooks, and verify SessionStart prints the CSE stance with the repository role, confirmed agent role, and AGENTS.md CSE Protocol pointer.",
        "claude": "Fresh Claude Code check: close the current session, open a new session in this repository with the plugin loaded, and verify SessionStart prints the CSE stance with the repository role, confirmed agent role, and AGENTS.md CSE Protocol pointer.",
    }[agent]
    trust = {"codex_hook_trust": codex_trust_report(root)} if agent == "codex" else {}
    return {**trust, "agent": agent, "project": str(root), "configuration": str(target),
            "configuration_current": current, "configuration_sources": sources,
            "inspection_home": str(home), "home_matches_environment": home == Path.home().resolve(),
            "runtime": runtime, "dependencies": {name: shutil.which(name) for name in (agent, "python3", "git")},
            "managed_protocol": {
                "block": routing["block"],
                "repository_role": routing["repository_role"],
                "agent_role": routing["agent_role"] or "missing",
                "missing": routing["missing"],
                "satisfied": routing["satisfied"],
            },
            "trust_and_activation": "unverified: installed files and registrations do not prove host trust, active-session loading, or observed hook execution",
            "fresh_session_check": fresh_session_check,
            "not_inspected": ["plugin-bundled hooks", "managed and ancestor configuration", "active task loaded state"],
            "scope": "on-disk files only; command targets use inspection_home, while execution uses the host's HOME; saved plugin disables do not disable project hooks"}


def trust_codex_hooks(root: Path, source: Path | None = None) -> None:
    """Best effort: the registration stays in place if Codex trust cannot be recorded."""
    try:
        hooks, newly = codex_cse_hooks(root, trust=True, source=source)
    except InstallError as exc:
        print(f"warning: could not record Codex hook trust: {exc}. {SKIPPED_UNTRUSTED}", file=sys.stderr)
        return
    for hook in hooks:
        label = "trusted" if hook["key"] in newly else "already " + hook["trustStatus"]
        print(f"{label}: {hook['key']}")
    if not hooks or any(h["trustStatus"] != "trusted" for h in hooks):
        print(f"warning: {NO_HOOKS_LISTED if not hooks else 'some CSE hooks are not trusted'}. {SKIPPED_UNTRUSTED}",
              file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", type=Path, default=Path.home())
    parser.add_argument("--replace-runtime", action="store_true")
    parser.add_argument("--repo", type=Path, action="append", default=[])
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--agent", choices=tuple(CONFIG_PATHS), default="codex")
    parser.add_argument("--diagnose", action="store_true", help="read-only installation report; does not run hooks")
    parser.add_argument("--user", action="store_true",
                        help="register in the user configuration under --home, active in every CSE repository")
    parser.add_argument("--remove", action="store_true",
                        help="remove the CSE registrations from --repo targets or the user configuration")
    args = parser.parse_args()
    try:
        validate_sources()
        if args.diagnose:
            print(json.dumps([diagnose(repo, args.home, args.agent) for repo in (args.repo or [Path.cwd()])], indent=2))
            return 0
        if args.check:
            print("CSE hook sources validated")
            return 0
        user = args.home.resolve() / CONFIG_PATHS[args.agent]
        for repository in args.repo:
            merged_configuration(project_root(repository) / CONFIG_PATHS[args.agent], args.agent)
        if args.user:
            merged_configuration(user, args.agent)
        if args.remove:
            targets = [*(project_root(r) / CONFIG_PATHS[args.agent] for r in args.repo), *([user] if args.user else [])]
            for target in targets:
                target, status = write_registration(target, args.agent, add=False)
                print(f"{status}: {target}")
            return 0
        for target, status in install_runtime(args.home, args.replace_runtime):
            print(f"{status}: {target}")
        for repository in args.repo:
            target, status = install_repository(repository, args.agent)
            print(f"{status}: {target}")
            if args.agent == "codex":
                trust_codex_hooks(project_root(repository))
        if args.user:
            target, status = write_registration(user, args.agent, add=True)
            print(f"{status}: {target}")
            if args.agent == "codex":
                # User hooks are listed for any trusted working directory; list from this one.
                trust_codex_hooks(Path.cwd().resolve(), source=user)
    except (InstallError, OSError, json.JSONDecodeError, subprocess.TimeoutExpired) as exc:
        parser.exit(1, f"CSE hook installation failed: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
