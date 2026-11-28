#!/usr/bin/env python3
"""Record local check_prose.py counts for working papers and compare past revisions."""

import argparse
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import tomllib


CHECKER = Path(__file__).with_name("check_prose.py").resolve()
CONFIG_EXAMPLE = """Config example:
  [[manuscripts]]
  name = "Example"
  root = "~/work/example"
  path = "paper/main.tex"  # Relative to root.

  # Optional. Repeat to compare more revisions of this manuscript.
  [[manuscripts.pairs]]
  bad = "BAD_COMMIT"
  good = "GOOD_COMMIT"
  drops = ["paragraph-length"]
"""


def scan(root, path):
    manuscript = (root / path).resolve()
    if path.is_absolute() or not manuscript.is_relative_to(root) or not manuscript.is_file() or manuscript.suffix.lower() != ".tex":
        raise ValueError(f"expected a manuscript .tex path relative to {root}: {path}")
    result = subprocess.run(
        [sys.executable, str(CHECKER), "--root", str(root), "--summary-json", str(manuscript)],
        cwd=root, capture_output=True, text=True,
    )
    if result.returncode not in (0, 1):  # Status 1 still reports counts alongside terminology violations.
        raise ValueError(result.stderr.strip() or result.stdout.strip() or f"checker exited {result.returncode}")
    return json.loads(result.stdout)


def commit_at(root, revision):
    return subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", "--verify", "--end-of-options", f"{revision}^{{commit}}"],
        text=True, stderr=subprocess.PIPE,
    ).strip()


def scan_commit(root, path, commit):
    with tempfile.TemporaryDirectory(prefix="cse-manuscript-") as directory, tempfile.TemporaryFile() as archive:
        subprocess.run(
            ["git", "-C", str(root), "archive", "--format=tar", commit],
            stdout=archive, stderr=subprocess.PIPE, text=True, check=True,
        )
        archive.seek(0)
        with tarfile.open(fileobj=archive) as snapshot:
            snapshot.extractall(directory, filter="data")
        return scan(Path(directory).resolve(), path)


def record_run(history, current):
    history.parent.mkdir(parents=True, exist_ok=True)
    with history.open("a+", encoding="utf-8") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        stream.seek(0)
        previous = {}
        for line in stream:
            previous.update(json.loads(line)["manuscripts"])
        stream.write(json.dumps({
            "date": datetime.now(timezone.utc).isoformat(),
            "manuscripts": current,
        }) + "\n")
    return previous


def compare_pair(name, root, path, pair):
    kinds = pair["drops"]
    if not isinstance(kinds, list) or not kinds or any(not isinstance(kind, str) for kind in kinds):
        raise ValueError("each pair needs at least one warning kind in drops")
    drops = set(kinds)
    bad, good = (commit_at(root, pair[side]) for side in ("bad", "good"))
    before, after = (scan_commit(root, path, commit) for commit in (bad, good))
    old, new = before["kinds"], after["kinds"]
    missed = sorted(kind for kind in drops if new.get(kind, 0) >= old.get(kind, 0))
    counts = ", ".join(
        f"{kind} {old.get(kind, 0)}→{new.get(kind, 0)}" for kind in sorted(old.keys() | new.keys() | drops)
    )
    status = "FAIL (" + ", ".join(missed) + " did not drop)" if missed else "PASS"
    print(f"{name} {bad[:9]}→{good[:9]}  {status}  {counts}")
    if before["scan_notices"] or after["scan_notices"]:
        print(f"  Checker scan notices {before['scan_notices']}→{after['scan_notices']}")
    return bool(missed)


def main():
    config = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "cse/manuscripts.toml"
    history = Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local/state") / "cse/manuscript-health.jsonl"
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"Config: {config}\nHistory: {history}\n\n{CONFIG_EXAMPLE}",
    )
    parser.parse_args()
    os.umask(0o077)
    errors = (OSError, ValueError, KeyError, TypeError, tarfile.TarError, subprocess.CalledProcessError)
    try:
        with config.open("rb") as stream:
            manuscripts = tomllib.load(stream)["manuscripts"]
        if not manuscripts:
            raise ValueError(f"no manuscripts configured in {config}")
        current = {}
        comparisons = []
        failed = False
        for item in manuscripts:
            name, root, path = item["name"], Path(item["root"]).expanduser().resolve(), Path(item["path"])
            key = str((root / path).resolve())
            comparisons.extend((name, root, path, pair) for pair in item.get("pairs", []))
            try:
                commit = commit_at(root, "HEAD")
                current[key] = {"name": name, "commit": commit, **scan(root, path)}
            except errors as error:
                print(f"{name}: {error}", file=sys.stderr)
                failed = True

        if current:
            previous = record_run(history, current)
            width = max(len("Manuscript"), *(len(row["name"]) for row in current.values()))
            print(f"{'Manuscript':<{width}}  Advisories  Change  Counts by kind")
            for key, row in current.items():
                new = row["kinds"]
                old = previous[key]["kinds"] if key in previous else None
                delta = "—" if old is None else f"{sum(new.values()) - sum(old.values()):+d}"
                counts = []
                for kind in sorted(new.keys() | (old or {}).keys()):
                    count = new.get(kind, 0)
                    change = count - old.get(kind, 0) if old is not None else 0
                    counts.append(f"{kind} {count} ({change:+d})" if change else f"{kind} {count}")
                print(f"{row['name']:<{width}}  {sum(new.values()):>10}  {delta:>6}  {', '.join(counts) or '—'}")
                if row["scan_notices"]:
                    print(f"{'':<{width}}  Checker scan notices {row['scan_notices']}")

        if comparisons:
            print("\nHistorical comparisons (bad → good)")
        for name, root, path, pair in comparisons:
            try:
                failed |= compare_pair(name, root, path, pair)
            except errors as error:
                print(f"{name} pair: {error}", file=sys.stderr)
                failed = True
        return int(failed)
    except errors as error:
        print(f"Manuscript health: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
