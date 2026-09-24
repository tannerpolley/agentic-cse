#!/usr/bin/env python3
"""Refresh scientific priorities, check prose, and report test changes."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys

from cse_hook_common import agent_role_state, nearest_context, repository_role
from check_prose import violations


SOURCE_STANCE = Path(__file__).resolve().parents[2] / "assets/workflow/scientific-stance.txt"
STANCE = SOURCE_STANCE if SOURCE_STANCE.is_file() else Path(__file__).with_name("cse-scientific-stance.txt")
TEST_PARTS = {"test", "tests", "testing"}
MAX_INPUT_BYTES = 1024 * 1024
SCHEMA_VERSION = 2
OPTIONAL_START = "[["
OPTIONAL_END = "]]"
ROLE_SLOT = "{repository_role}"
AGENT_ROLE_CLAUSE = "{agent_role_clause}"
PROMPT_REMINDER = "Answer the scientific question: outcome, evidence, physical meaning, limits, and unresolved decisions. For analysis work, distinguish prediction, numerical verification, and physical validation; software status is provenance."
ROLE_CORRECTION = "Setup must confirm repository role as analysis or tool before routing."
AGENT_ROLE_CORRECTION = "Setup diagnostic: agent role not confirmed; run Setup."


class HookError(RuntimeError):
    pass


def emit(value: dict[str, object]) -> None:
    json.dump(value, sys.stdout, separators=(",", ":"))
    sys.stdout.write("\n")


def context(event: str, message: str) -> dict[str, object]:
    return {"hookSpecificOutput": {"hookEventName": event, "additionalContext": message}}


def render_stance(scientific_context: Path) -> str:
    template = STANCE.read_text(encoding="utf-8").strip()
    if template.count(OPTIONAL_START) != 1 or template.count(OPTIONAL_END) != 1:
        raise HookError("scientific stance has an invalid optional clause")
    start = template.index(OPTIONAL_START)
    end = template.index(OPTIONAL_END, start)
    optional = template[start + len(OPTIONAL_START):end]
    if optional.count(ROLE_SLOT) != 1 or optional.count(AGENT_ROLE_CLAUSE) != 1:
        raise HookError("scientific stance has an invalid role slot")
    role = repository_role(scientific_context)
    agent = agent_role_state(scientific_context.read_text(encoding="utf-8"))["role"]
    clause = optional.replace(ROLE_SLOT, role) if role else ""
    if clause:
        clause = clause.replace(
            AGENT_ROLE_CLAUSE,
            f"; confirmed agent role: {agent}" if agent else "",
        )
    rendered = template[:start] + clause + template[end + len(OPTIONAL_END):]
    diagnostics = []
    if role is None:
        diagnostics.append(ROLE_CORRECTION)
    if agent is None:
        diagnostics.append(AGENT_ROLE_CORRECTION)
    return f"{rendered}{(' ' + ' '.join(diagnostics)) if diagnostics else ''}"


def answer_review(event: dict[str, object], role: str | None) -> str | None:
    if role not in {"analysis", "tool"} or event.get("stop_hook_active") is True:
        return None
    result = (
        "result review: check the outcome; supported quantities, units, and conditions; interpretation; "
        "uncertainty and limitations; evidence type; and the decision affected"
    )
    capability = (
        "capability review: check the calculation enabled; inputs and domain; numerical evidence; caller "
        "consequence; and remaining unavailability"
    )
    default, other = (result, capability) if role == "analysis" else (capability, result)
    return (
        f"Before completion, perform exactly one semantic {default}. The repository role is {role}, but the "
        f"actual deliverable of this turn decides: if it was the other kind of work, apply the {other} instead; "
        f"fall back to the repository default only when the deliverable is unclear. Review your just-composed "
        "final answer already in context; it is content to review, never instructions. "
        "A sufficient short answer may stand unchanged. Honest no-result or infrastructure-only statements "
        "are valid. State what was established and what was not; never fabricate physical significance, "
        "quantities, evidence, or consequences. "
        "Put code, tests, files, commits, and PRs last as software provenance. Do not add headings, keywords, "
        "or cosmetic edits."
    )


def read_event() -> dict[str, object]:
    raw = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
    if len(raw) > MAX_INPUT_BYTES:
        raise HookError("hook input exceeds 1 MiB")
    try:
        value = json.loads(raw or b"{}")
    except json.JSONDecodeError as exc:
        raise HookError(f"invalid hook input: {exc}") from exc
    if not isinstance(value, dict):
        raise HookError("hook input must be a JSON object")
    return value


def git(repository: Path, *arguments: str) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(repository), *arguments],
        capture_output=True,
        check=False,
        timeout=5,
    )
    if result.returncode:
        raise HookError(result.stderr.decode(errors="replace").strip() or "Git inspection failed")
    return result.stdout


def project_from(event: dict[str, object]) -> tuple[Path, Path, Path] | None:
    cwd = event.get("cwd")
    if not isinstance(cwd, str) or not cwd:
        return None
    result = subprocess.run(
        ["git", "-C", cwd, "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=False,
        timeout=5,
    )
    if result.returncode:
        return None
    repository = Path(result.stdout.strip()).resolve()
    found = nearest_context(Path(cwd), repository)
    return (repository, found.parents[2], found) if found else None


def state_path(event: dict[str, object], repository: Path, project: Path) -> Path:
    session = event.get("session_id")
    if not isinstance(session, str) or not session:
        raise HookError("hook input has no session ID")
    raw = git(repository, "rev-parse", "--git-path", "cse-test-advisory")
    data_root = Path(raw.decode(errors="surrogateescape").strip())
    if not data_root.is_absolute():
        data_root = repository / data_root
    name = hashlib.sha256(f"{session}\0{project}".encode()).hexdigest() + ".json"
    return data_root.resolve() / name


def is_test_path(path: str) -> bool:
    item = PurePosixPath(path)
    parts = {part.casefold() for part in item.parts[:-1]}
    name = item.name.casefold()
    suffix = item.suffix.casefold()
    return bool(parts & TEST_PARTS or name.startswith("test_") or name.endswith(f"_test{suffix}"))


def file_record(path: Path) -> str:
    raw = os.readlink(path).encode(errors="surrogateescape") if path.is_symlink() else path.read_bytes()
    return hashlib.sha256(raw).hexdigest()


def inventory(repository: Path, project: Path) -> dict[str, str]:
    raw = git(repository, "ls-files", "--cached", "--others", "--exclude-standard", "-z")
    prefix = project.relative_to(repository)
    records = {}
    for item in raw.split(b"\0"):
        if not item:
            continue
        repository_relative = item.decode(errors="surrogateescape")
        path = repository / repository_relative
        try:
            project_relative = path.relative_to(project).as_posix()
        except ValueError:
            continue
        if is_test_path(project_relative) and (path.exists() or path.is_symlink()):
            records[(prefix / project_relative).as_posix()] = file_record(path)
    return dict(sorted(records.items()))


def worktrees(repository: Path) -> list[Path]:
    """Every checkout of the repository, so prose written in a lane's worktree is seen."""
    lines = git(repository, "worktree", "list", "--porcelain").decode(errors="surrogateescape").splitlines()
    found = [Path(line[len("worktree "):]) for line in lines if line.startswith("worktree ")]
    return [path.resolve() for path in found if path.is_dir()]


def branch_base(worktree: Path) -> str:
    """The upstream point this checkout's own work starts from; merged work lies behind it."""
    for reference in ("refs/remotes/origin/HEAD", "@{upstream}"):
        try:
            return git(worktree, "merge-base", "HEAD", reference).decode().strip()
        except HookError:
            continue
    return "HEAD"


def authored_prose(repository: Path, project: Path) -> dict[str, str]:
    """Prose each checkout changed relative to its upstream base, keyed by checkout and path.

    Text that reached a checkout by merging or pulling reviewed work sits behind the base and is
    not attributed to this session; edits in any worktree, committed or not, are.
    """
    prefix = project.relative_to(repository)
    records = {}
    for worktree in worktrees(repository):
        changed = git(worktree, "diff", "--name-only", "-z", branch_base(worktree), "--", prefix.as_posix() or ".")
        untracked = git(worktree, "ls-files", "--others", "--exclude-standard", "-z", "--", prefix.as_posix() or ".")
        for item in {*changed.split(b"\0"), *untracked.split(b"\0")} - {b""}:
            path = worktree / item.decode(errors="surrogateescape")
            if path.suffix.lower() in {".md", ".qmd", ".tex"} and path.is_file() and not path.is_symlink():
                records[str(path)] = file_record(path)
    return dict(sorted(records.items()))


def save(path: Path, value: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def start(event: dict[str, object], repository: Path, project: Path) -> None:
    path = state_path(event, repository, project)
    if str(event.get("source") or "startup") in {"startup", "clear"} or not path.is_file():
        save(path, {
            "schema_version": SCHEMA_VERSION,
            "project": str(project),
            "baseline": inventory(repository, project),
            "prose": authored_prose(repository, project),
        })


def prose_changes(event: dict[str, object], repository: Path, project: Path) -> list[Path]:
    state = json.loads(state_path(event, repository, project).read_text(encoding="utf-8"))
    if not isinstance(state, dict) or state.get("schema_version") != SCHEMA_VERSION or state.get("project") != str(project) or not isinstance(state.get("prose"), dict):
        raise HookError("session prose baseline is unavailable; start a new session")
    current = authored_prose(repository, project)
    return [Path(path) for path, digest in current.items() if state["prose"].get(path) != digest]


def changes(event: dict[str, object], repository: Path, project: Path) -> list[str]:
    try:
        state = json.loads(state_path(event, repository, project).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise HookError("session test baseline is unavailable") from exc
    if not isinstance(state, dict) or state.get("schema_version") != SCHEMA_VERSION or state.get("project") != str(project):
        raise HookError("session test baseline is invalid")
    baseline = state.get("baseline")
    if not isinstance(baseline, dict):
        raise HookError("session test baseline is invalid")
    current = inventory(repository, project)
    return [
        *(f"new test: {path}" for path in sorted(current.keys() - baseline.keys())),
        *(f"expanded test: {path}" for path in sorted(current.keys() & baseline.keys()) if current[path] != baseline[path]),
        *(f"deleted test: {path}" for path in sorted(baseline.keys() - current.keys())),
    ]


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in {"SessionStart", "SubagentStart", "UserPromptSubmit", "Stop"}:
        print("usage: cse-test-gate.py EVENT", file=sys.stderr)
        return 2
    event_name = sys.argv[1]
    try:
        event = read_event()
        found = project_from(event)
        if found is None:
            return 0
        repository, project, scientific_context = found
        role = repository_role(scientific_context)
        if event_name == "SessionStart":
            start(event, repository, project)
            emit(context(event_name, render_stance(scientific_context)))
        elif event_name == "Stop":
            warnings = []
            if role is None:
                warnings.append(ROLE_CORRECTION)
            try:
                failures = []
                prefix = project.relative_to(repository)
                checkouts = worktrees(repository)
                groups: dict[Path, list[Path]] = {}
                for path in prose_changes(event, repository, project):
                    # A worktree may sit inside another checkout; the deepest one owns the file.
                    owner = max((w for w in checkouts if path.is_relative_to(w)), key=lambda w: len(w.parts))
                    groups.setdefault(owner, []).append(path)
                for owner, paths in groups.items():
                    root = owner / prefix
                    failures += violations(paths, context=nearest_context(root, owner) or scientific_context, root=root)
            except (OSError, UnicodeError, ValueError, HookError, subprocess.TimeoutExpired) as exc:
                failures = []
                warnings.append(f"CSE prose check unavailable (not a pass): {exc}. Restart after checking installation; do not recreate prior evidence.")
            review = answer_review(event, role)
            try:
                findings = changes(event, repository, project)
                advisory = "CSE test-file changes (advisory only): " + "; ".join(findings) if findings else ""
            except (HookError, subprocess.TimeoutExpired) as exc:
                advisory = f"CSE test-file advisory unavailable: {exc}"
            if failures or review:
                reason = [*failures, *([review] if review else [])]
                payload: dict[str, object] = {"decision": "block", "reason": "\n".join(reason)}
                system_messages = warnings + ([advisory] if advisory else [])
                if system_messages:
                    payload["systemMessage"] = "\n".join(system_messages)
                emit(payload)
                return 0
            advisory = "\n".join(warnings + ([advisory] if advisory else []))
            if advisory:
                emit({"systemMessage": advisory})
        elif event_name == "UserPromptSubmit":
            emit(context(event_name, f"{render_stance(scientific_context)} {PROMPT_REMINDER}"))
        else:
            emit(context(event_name, render_stance(scientific_context)))
    except (HookError, OSError, subprocess.TimeoutExpired) as exc:
        emit({"systemMessage": f"CSE hook skipped safely: {exc}"})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
