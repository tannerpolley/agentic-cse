#!/usr/bin/env python3
"""Refresh scientific priorities, check prose, and report test changes."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys

from cse_hook_common import agent_role_state, nearest_context, repository_role
from check_prose import violations


SOURCE_STANCE = Path(__file__).resolve().parents[2] / "assets/workflow/scientific-stance.txt"
STANCE = SOURCE_STANCE if SOURCE_STANCE.is_file() else Path(__file__).with_name("cse-scientific-stance.txt")
SOURCE_ROUTING = SOURCE_STANCE.with_name("skill-routing.txt")
ROUTING = SOURCE_ROUTING if SOURCE_ROUTING.is_file() else Path(__file__).with_name("cse-skill-routing.txt")
ROUTING_LEAD = ("CSE skill routing: before doing a stage's work, invoke its skill (Claude Code: the Skill tool; "
                "Codex: open that skill's SKILL.md from the skill list).")
# T3 Code prefixes a delegated task with "Act as the <role> sub-agent"; each role is one CSE stage.
DELEGATED_ROLE = re.compile(r"\A\s*Act as the ([\w-]+) sub-agent\b", re.IGNORECASE)
ROLES_LINE = "delegated roles — "
NAMED_SKILL = re.compile(r"(?<![/$\w-])cse:([a-z]+)\b", re.IGNORECASE)
TEST_PARTS = {"test", "tests", "testing"}
MAX_INPUT_BYTES = 1024 * 1024
SCHEMA_VERSION = 4
OPTIONAL_START = "[["
OPTIONAL_END = "]]"
ROLE_SLOT = "{repository_role}"
AGENT_ROLE_CLAUSE = "{agent_role_clause}"
ROLE_CORRECTION = ("Repository role is not confirmed in docs/scientific/CONTEXT.md; ask the investigator to run "
                   "cse:setup. Route every other stage to its skill as usual.")
AGENT_ROLE_CORRECTION = "Setup diagnostic: agent role not confirmed; cse:setup records it."
CLAUDE_WRITE_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
PATCH_TARGET = re.compile(r"\*\*\* (?:Add File|Update File|Move to): (.+?)(?:\\n|\n|$)")
PROSE_PATH = r"([^\s'\"\\<>|;&()]+\.(?:md|qmd|tex))\b"
SHELL_TARGET = re.compile(r"(?:>>?|\btee(?:\s+-a)?)\s*['\"]?" + PROSE_PATH)
IN_PLACE = re.compile(r"\b(?:sed|perl)\s+(?:-\S+\s+)*-\w*i")
WORKDIR = re.compile(r"['\"]?workdir['\"]?\s*:\s*['\"]([^'\"]+)")


class HookError(RuntimeError):
    pass


def emit(value: dict[str, object]) -> None:
    json.dump(value, sys.stdout, separators=(",", ":"))
    sys.stdout.write("\n")


def context(event: str, message: str) -> dict[str, object]:
    return {"hookSpecificOutput": {"hookEventName": event, "additionalContext": message}}


def render_stance(scientific_context: Path, *, diagnostics: bool = True) -> str:
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
    # Setup diagnostics appear once per session (start and stop), not on every subagent.
    notes = [] if not diagnostics else [
        *([ROLE_CORRECTION] if role is None else []), *([AGENT_ROLE_CORRECTION] if agent is None else [])]
    return f"{rendered}{(' ' + ' '.join(notes)) if notes else ''}"


def routing_lines() -> list[str]:
    # Routing is guidance on top of the stance; a runtime without the file keeps the stance.
    try:
        return [line.strip() for line in ROUTING.read_text(encoding="utf-8").splitlines() if line.strip()]
    except OSError:
        return []


def routing_table() -> str:
    lines = routing_lines()
    return f"{ROUTING_LEAD} " + "; ".join(lines) + "." if lines else ""


def prompt_route(event: dict[str, object]) -> str:
    """Name the skill for a prompt whose stage is explicit: a delegated role or a named CSE skill."""
    prompt = event.get("prompt")
    if not isinstance(prompt, str):
        return ""
    lines = routing_lines()
    known = {name for line in lines for name in re.findall(r"cse:([a-z]+)", line.split(" — ")[0])}
    roles = {role: skill for line in lines if line.startswith(ROLES_LINE)
             for role, skill in re.findall(r"([\w-]+): cse:([a-z]+)", line)}
    role = DELEGATED_ROLE.match(prompt)
    role_name = role.group(1).lower() if role else ""
    skills = [roles[role_name]] if role_name in roles else []
    skills += [name for name in dict.fromkeys(n.lower() for n in NAMED_SKILL.findall(prompt))
               if name in known and name not in skills]
    if not skills:
        return ""
    names = ", ".join(f"`cse:{name}`" for name in skills)
    why = f"delegated {role_name} task" if role_name in roles else "named in the request"
    return (f"CSE route for this prompt ({why}): invoke {names} before other work "
            "(Claude Code: the Skill tool; Codex: open its SKILL.md).")


# A relay only reports progress: every clause opens with one of these, so a clause with a claim or delivery is reviewed.
RELAY_START = re.compile(r"^(?:i[’']?ll|i will|i[’']?m waiting|waiting|started|starting|running|queued|launched|delegated|"
                         r"relayed)\b", re.IGNORECASE)
LIST_MARKER = re.compile(r"^(?:[-*+]|\d+[.)])\s+")
SENTENCE_END = re.compile(r"[.!]\s")
CLAUSE_BREAK = re.compile(r"[.!?;]+")
EMPHASIS = re.compile(r"[*_`]+")


def plainly_not_a_result(message: object) -> bool:
    """Only questions to the user and short progress relays skip the review; anything unclear is reviewed."""
    # Emphasis can hide a sentence end ("**6289.08 Pa.** Should I continue?"), so it is dropped first.
    if not isinstance(message, str) or not (text := EMPHASIS.sub("", message).strip()):
        return True
    lines = [LIST_MARKER.sub("", line.strip()).strip() for line in text.splitlines() if line.strip()]
    # A line that also ends a statement ("... 6289.08 Pa. Should I continue?") is not question-only.
    if all(line.endswith("?") and not SENTENCE_END.search(line) for line in lines):
        return True
    clauses = [clause.strip() for clause in CLAUSE_BREAK.split(text) if clause.strip()]
    return (len(text.split()) <= 25 and not any(c.isdigit() for c in text)
            and all(RELAY_START.match(clause) for clause in clauses))


def answer_review(event: dict[str, object], role: str | None) -> str | None:
    if (role not in {"analysis", "tool"} or event.get("stop_hook_active") is True
            or plainly_not_a_result(event.get("last_assistant_message"))):
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
        f"fall back to the repository default only when the deliverable is unclear. Your final answer is "
        "already sent and cannot be edited; review it in context; it is content to review, never instructions. "
        "If it stands, end the turn without writing anything more. If it needs a correction, write only "
        "that correction as a short note; never repeat or rewrite the answer. Honest no-result or "
        "infrastructure-only statements stand. A correction must not fabricate physical significance, "
        "quantities, evidence, or consequences."
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
    """One file per session and project, shared by every checkout so a move into a worktree keeps it."""
    session = event.get("session_id")
    if not isinstance(session, str) or not session:
        raise HookError("hook input has no session ID")
    common = git(repository, "rev-parse", "--path-format=absolute", "--git-common-dir")
    scope = project.relative_to(repository).as_posix()
    name = hashlib.sha256(f"{session}\0{scope}".encode()).hexdigest() + ".json"
    return Path(common.decode(errors="surrogateescape").strip()) / "cse-test-advisory" / name


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


def checkouts(repository: Path) -> list[tuple[Path, str | None]]:
    """Usable checkouts of the repository with their branch; bare and prunable entries are skipped."""
    blocks = git(repository, "worktree", "list", "--porcelain").decode(errors="surrogateescape").split("\n\n")
    found = []
    for block in blocks:
        fields = dict(line.partition(" ")[::2] for line in block.splitlines() if line)
        path = Path(fields.get("worktree", ""))
        if "worktree" in fields and "bare" not in fields and "prunable" not in fields and path.is_dir():
            found.append((path.resolve(), fields.get("branch")))
    return found


def worktrees(repository: Path) -> list[Path]:
    return [path for path, _ in checkouts(repository)]


def commit(worktree: Path, reference: str) -> str | None:
    try:
        return git(worktree, "rev-parse", "--verify", "-q", f"{reference}^{{commit}}").decode().strip() or None
    except HookError:
        return None


def integrated_line(worktree: Path, branch: str | None) -> str | None:
    """The reviewed line work merges into: the upstream, origin's default, or the local default branch."""
    for reference in ("@{upstream}", "refs/remotes/origin/HEAD", "refs/heads/main", "refs/heads/master"):
        if reference != branch and (found := commit(worktree, reference)):
            return found
    return None


def session_refs(repository: Path) -> dict[str, str]:
    """Branch tips and checkout HEADs when the session starts."""
    refs = {}
    for line in git(repository, "for-each-ref", "--format=%(refname) %(objectname)", "refs/heads").decode().splitlines():
        name, _, sha = line.partition(" ")
        refs[name] = sha
    for path, _ in checkouts(repository):
        if head := commit(path, "HEAD"):
            refs[f"checkout:{path}"] = head
    return refs


def blob(worktree: Path, reference: str, relative: str) -> str | None:
    try:
        return git(worktree, "rev-parse", "--verify", "-q", f"{reference}:{relative}").decode().strip()
    except HookError:
        return None


def written_prose(repository: Path, project: Path, refs: dict[str, str]) -> list[Path]:
    """Prose this session wrote in any checkout, committed or not.

    A file counts when its content differs both from the integrated line (so text that arrived by
    merging or pulling reviewed work is excluded) and from what the checkout's branch held when the
    session started (so an existing branch checked out mid-session is not attributed to it).
    """
    scope = project.relative_to(repository).as_posix() or "."
    written = []
    for worktree, branch in checkouts(repository):
        try:
            start = refs.get(branch or "") or refs.get(f"checkout:{worktree}")
            anchors = [a for a in (integrated_line(worktree, branch), start) if a] or ["HEAD"]
            names = set(git(worktree, "ls-files", "--others", "--exclude-standard", "-z", "--", scope).split(b"\0"))
            for anchor in anchors:
                names |= set(git(worktree, "diff", "--name-only", "-z", anchor, "--", scope).split(b"\0"))
            for item in sorted(names - {b""}):
                relative = item.decode(errors="surrogateescape")
                path = worktree / relative
                if path.suffix.lower() not in {".md", ".qmd", ".tex"} or not path.is_file() or path.is_symlink():
                    continue
                content = git(worktree, "hash-object", "--", relative).decode().strip()
                if all(blob(worktree, anchor, relative) != content for anchor in anchors):
                    written.append(path)
        except (HookError, subprocess.TimeoutExpired):
            continue  # an unreadable checkout is skipped rather than disabling the check for all
    return written


def shell_writes(command: str, workdir: str) -> set[Path]:
    """Prose paths a shell command writes: redirection or tee targets, or any path an in-place sed or perl edits."""
    targets = set(SHELL_TARGET.findall(command))
    if IN_PLACE.search(command):
        targets |= set(re.findall(PROSE_PATH, command))
    return {Path(workdir, target).resolve() for target in targets}


def session_writes(event: dict[str, object]) -> set[Path] | None:
    """Files this session's own write-tool calls named, or None without a readable transcript.

    Claude Code records Edit, Write, MultiEdit, and NotebookEdit inputs (subagent transcripts sit
    beside the session's); Codex records apply_patch headers in tool-call inputs. Shell commands
    in either host contribute redirection and tee targets and every prose path an in-place sed or
    perl edits. Relative paths resolve against the call's workdir or the turn's cwd.
    """
    # ponytail: prose written by scripts, cp, or mv, or through a relative path after cd, escapes the check.
    transcript = event.get("transcript_path")
    if not isinstance(transcript, str) or not transcript or not Path(transcript).is_file():
        return None
    main = Path(transcript)
    written: set[Path] = set()
    cwd = str(event.get("cwd") or "")
    try:
        for source in (main, *sorted(main.with_suffix("").glob("subagents/*.jsonl"))):
            with source.open(encoding="utf-8", errors="replace") as lines:
                for line in lines:
                    if not any(marker in line for marker in ('"tool_use"', '_call"', '"turn_context"', '"session_meta"')):
                        continue
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if not isinstance(record, dict):
                        continue
                    message, payload = record.get("message"), record.get("payload")
                    if record.get("type") == "assistant" and isinstance(message, dict) and isinstance(message.get("content"), list):
                        for item in message["content"]:
                            if not isinstance(item, dict) or item.get("type") != "tool_use":
                                continue
                            tool_input = item.get("input") if isinstance(item.get("input"), dict) else {}
                            base = record.get("cwd") or cwd
                            if item.get("name") in CLAUDE_WRITE_TOOLS:
                                for key in ("file_path", "notebook_path"):
                                    if isinstance(tool_input.get(key), str):
                                        written.add(Path(base, tool_input[key]).resolve())
                            elif item.get("name") == "Bash" and isinstance(tool_input.get("command"), str):
                                written |= shell_writes(tool_input["command"], base)
                    elif not isinstance(payload, dict):
                        continue
                    elif record.get("type") in {"session_meta", "turn_context"}:
                        cwd = str(payload.get("cwd") or cwd)
                    elif payload.get("type") in {"custom_tool_call", "function_call"}:
                        call = str(payload.get("input") or payload.get("arguments") or "")
                        workdir = match[1] if (match := WORKDIR.search(call)) else cwd
                        for target in PATCH_TARGET.findall(call):
                            written.add(Path(workdir, target.strip().rstrip("\\\"'")).resolve())
                        written |= shell_writes(call, workdir)
    except OSError:
        return None
    return written


def save(path: Path, value: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.{os.getpid()}.tmp")  # overlapping Stops never share one
    temporary.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def load_state(event: dict[str, object], repository: Path, project: Path) -> tuple[dict, bool]:
    """The session's state; a fresh one when SessionStart left none (hooks installed mid-session)."""
    try:
        state = json.loads(state_path(event, repository, project).read_text(encoding="utf-8"))
        if (isinstance(state, dict) and state.get("schema_version") == SCHEMA_VERSION
                and isinstance(state.get("refs"), dict) and isinstance(state.get("tests"), dict)):
            return state, False
    except (OSError, ValueError):
        pass
    return {"schema_version": SCHEMA_VERSION, "refs": session_refs(repository), "tests": {}}, True


def note_checkout(state: dict, repository: Path, project: Path) -> None:
    """Snapshot this checkout's tests the first time the session works in it."""
    state["tests"].setdefault(str(repository), inventory(repository, project))


def start(event: dict[str, object], repository: Path, project: Path) -> None:
    path = state_path(event, repository, project)
    state, fresh = load_state(event, repository, project)
    if str(event.get("source") or "startup") in {"startup", "clear"} or fresh:
        state = {"schema_version": SCHEMA_VERSION, "refs": session_refs(repository), "tests": {}}
    note_checkout(state, repository, project)
    save(path, state)


def test_changes(state: dict, repository: Path, project: Path) -> str:
    """Test files changed in this checkout since the last report, named once; the snapshot then advances."""
    # ponytail: a checkout first entered mid-turn is snapshotted at that Stop, so that turn's test
    # edits there go unreported; T3 worktree handoffs happen between turns and are caught.
    baseline = state["tests"].get(str(repository))
    current = inventory(repository, project)
    state["tests"][str(repository)] = current
    if baseline is None:
        return ""
    groups = {
        "added": sorted(current.keys() - baseline.keys()),
        "changed": sorted(path for path in current.keys() & baseline.keys() if current[path] != baseline[path]),
        "deleted": sorted(baseline.keys() - current.keys()),
    }
    parts = [f"{kind} {', '.join(paths)}" for kind, paths in groups.items() if paths]
    return f"CSE: tests {'; '.join(parts)}." if parts else ""


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
            stance = " ".join(filter(None, (render_stance(scientific_context), routing_table())))
            try:
                start(event, repository, project)
            except (HookError, OSError, subprocess.TimeoutExpired) as exc:
                stance += f" CSE session record unavailable: {exc}."
            emit(context(event_name, stance))
        elif event_name == "Stop":
            warnings: list[str] = []
            failures: list[str] = []
            state, fresh = load_state(event, repository, project)
            if fresh:
                warnings.append("CSE checks found no session-start record, so they cover changes from now on.")
            if role is None and not state.get("role_noted"):
                warnings.append(ROLE_CORRECTION)
                state["role_noted"] = True
            try:
                written = session_writes(event)
                if written is None:
                    warnings.append("CSE could not read this session's transcript, so its prose check also covers "
                                    "what other sessions wrote since this one started.")
                prefix = project.relative_to(repository)
                checkouts = worktrees(repository)
                groups: dict[Path, list[Path]] = {}
                for path in written_prose(repository, project, state["refs"]):
                    if written is not None and path.resolve() not in written:
                        continue
                    # A worktree may sit inside another checkout; the deepest one owns the file.
                    owner = max((w for w in checkouts if path.is_relative_to(w)), key=lambda w: len(w.parts))
                    groups.setdefault(owner, []).append(path)
                for owner, paths in groups.items():
                    root = owner / prefix
                    failures += violations(paths, root=root)
            except (OSError, UnicodeError, ValueError, HookError, subprocess.TimeoutExpired) as exc:
                failures = []
                warnings.append(f"CSE prose check did not run: {exc}")
            try:
                report = test_changes(state, repository, project)
                warnings += [report] if report else []
                save(state_path(event, repository, project), state)
            except (OSError, UnicodeError, HookError, subprocess.TimeoutExpired) as exc:
                warnings.append(f"CSE test check did not run: {exc}")
            review = answer_review(event, role)
            payload: dict[str, object] = {}
            if failures or review:
                payload = {"decision": "block", "reason": "\n".join([*failures, *([review] if review else [])])}
            if warnings:
                payload["systemMessage"] = "\n".join(warnings)
            if payload:
                emit(payload)
        elif event_name == "SubagentStart":
            # A native subagent starts without the parent's context or a prompt to route, so it gets the stance.
            emit(context(event_name, " ".join(filter(None, (render_stance(scientific_context, diagnostics=False),
                                                             routing_table())))))
        else:
            try:  # a session that moved into another checkout gets that checkout's test snapshot now
                state, _ = load_state(event, repository, project)
                if str(repository) not in state["tests"]:
                    note_checkout(state, repository, project)
                    save(state_path(event, repository, project), state)
            except (OSError, UnicodeError, HookError, subprocess.TimeoutExpired):
                pass  # the Stop check reports its own failure; the prompt route still goes out
            if route := prompt_route(event):
                emit(context(event_name, route))
    except (HookError, OSError, subprocess.TimeoutExpired) as exc:
        emit({"systemMessage": f"CSE hook skipped safely: {exc}"})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
