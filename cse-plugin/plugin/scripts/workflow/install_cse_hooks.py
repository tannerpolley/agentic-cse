#!/usr/bin/env python3
"""Install the stable CSE hook runtime and opt CSE repositories into it."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import tomllib

from cse_hook_common import nearest_context
from setup_scientific_project import routing_report


ROOT = Path(__file__).resolve().parents[2]
RUNTIME_SOURCE = ROOT / "scripts/workflow/cse-test-gate.py"
COMMON_SOURCE = ROOT / "scripts/workflow/cse_hook_common.py"
PROSE_SOURCE = ROOT / "scripts/workflow/check_prose.py"
STANCE_SOURCE = ROOT / "assets/workflow/scientific-stance.txt"
CONFIG_SOURCE = ROOT / "assets/workflow/codex/hooks.json"
EVENTS = {"SessionStart", "SubagentStart", "UserPromptSubmit", "Stop"}
FORBIDDEN = ("plugins/cache", "PLUGIN_ROOT", "CLAUDE_PLUGIN_ROOT")
RUNTIME_DIRECTORY = Path(".local/share/cse/hooks")
CONFIG_PATHS = {"codex": Path(".codex/hooks.json"), "claude": Path(".claude/settings.json")}


class InstallError(RuntimeError):
    pass


def validate_sources() -> None:
    compile(RUNTIME_SOURCE.read_text(encoding="utf-8"), str(RUNTIME_SOURCE), "exec")
    compile(COMMON_SOURCE.read_text(encoding="utf-8"), str(COMMON_SOURCE), "exec")
    compile(PROSE_SOURCE.read_text(encoding="utf-8"), str(PROSE_SOURCE), "exec")
    stance = STANCE_SOURCE.read_text(encoding="utf-8").strip()
    if not stance or len(stance.split()) > 180:
        raise InstallError("scientific stance must contain 1 to 180 words")
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


def merged_configuration(target: Path, agent: str) -> dict:
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
    desired = configuration(agent)
    for event, groups in desired["hooks"].items():
        hooks.setdefault(event, []).extend(groups)
    if agent == "codex":
        result.setdefault("description", desired["description"])
    return result


def install_repository(path: Path, agent: str = "codex") -> tuple[Path, str]:
    root = project_root(path)
    target = root / CONFIG_PATHS[agent]
    content = (json.dumps(merged_configuration(target, agent), indent=2) + "\n").encode()
    if target.is_file() and target.read_bytes() == content:
        return target, "unchanged"
    atomic_write(target, content, 0o644)
    return target, "installed"


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
    return {"agent": agent, "project": str(root), "configuration": str(target),
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", type=Path, default=Path.home())
    parser.add_argument("--replace-runtime", action="store_true")
    parser.add_argument("--repo", type=Path, action="append", default=[])
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--agent", choices=tuple(CONFIG_PATHS), default="codex")
    parser.add_argument("--diagnose", action="store_true", help="read-only installation report; does not run hooks")
    args = parser.parse_args()
    try:
        validate_sources()
        if args.diagnose:
            print(json.dumps([diagnose(repo, args.home, args.agent) for repo in (args.repo or [Path.cwd()])], indent=2))
            return 0
        if args.check:
            print("CSE hook sources validated")
            return 0
        for repository in args.repo:
            merged_configuration(project_root(repository) / CONFIG_PATHS[args.agent], args.agent)
        for target, status in install_runtime(args.home, args.replace_runtime):
            print(f"{status}: {target}")
        for repository in args.repo:
            target, status = install_repository(repository, args.agent)
            print(f"{status}: {target}")
    except (InstallError, OSError, json.JSONDecodeError, subprocess.TimeoutExpired) as exc:
        parser.exit(1, f"CSE hook installation failed: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
