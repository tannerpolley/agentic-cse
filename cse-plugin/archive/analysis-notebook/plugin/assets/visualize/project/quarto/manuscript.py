#!/usr/bin/env python3
"""Manage the pages of a Quarto analysis website."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import tempfile

ASSET_ROOT = Path(__file__).resolve().parent
MEMBERSHIP = "_cse-manuscript.json"
RETIRED = ("preview.service", "_quarto-presentation.yml", ".cse-quarto-source.json")
IGNORES = ("/.quarto/", "/_site/", "/site_libs/", "/_freeze/", "/notebook.tex")
SITE_CONFIG = {
    "project": {"type": "website", "output-dir": "_site"},
    "metadata-files": [MEMBERSHIP],
    "website": {"title": "Analyses", "search": True, "reader-mode": True, "page-navigation": False},
    "format": {"html": {"embed-resources": True, "page-layout": "full", "theme": "cosmo", "css": "site.css",
                        "fontsize": "16px", "toc": True, "notebook-links": False, "format-links": False,
                        "html-math-method": "mathjax", "self-contained-math": True}},
    "execute": {"enabled": False},
}


def atomic_write(path: Path, data: bytes, mode: int = 0o644) -> None:
    with tempfile.TemporaryDirectory(dir=path.parent) as directory:
        staged = Path(directory) / path.name
        staged.write_bytes(data)
        staged.chmod(mode)
        staged.replace(path)


def save_membership(path: Path, contents: list) -> None:
    pages = [page["href"] for entry in contents for page in entry.get("contents", [entry])]
    sidebar = {"style": "docked", "collapse-level": 1, "contents": contents}
    state = {"project": {"render": pages}, "website": {"sidebar": sidebar}}
    atomic_write(path, (json.dumps(state, indent=2) + "\n").encode())


def init(root: Path) -> None:
    if not (root / "index.qmd").read_bytes().strip():
        raise ValueError(f"{root / 'index.qmd'}: expected a populated synthesis article")
    membership = root / MEMBERSHIP
    managed = membership.is_file()
    retired = [root / name for name in RETIRED if (root / name).is_file()]
    tooling = {name: (ASSET_ROOT / name).read_bytes() for name in ("manuscript.py", "render.sh")}
    for name in (*tooling, MEMBERSHIP, "_quarto.yml", "site.css", ".gitignore"):
        path = root / name
        if path.is_symlink() or (path.exists() and not path.is_file()):
            raise ValueError(f"{path}: expected a regular file")
        if not managed and name in tooling and path.exists() and path.read_bytes() != tooling[name]:
            raise ValueError(f"{path}: refusing to overwrite unmanaged tooling")

    if not managed:
        save_membership(membership, [{"text": "Home", "href": "index.qmd"}])
    elif retired:
        state = json.loads(membership.read_bytes())
        contents = state["website"]["sidebar"]["contents"]
        if "href" not in contents[0]:
            title_only = state.get("cse-title-only", [])

            def page_link(entry):
                return entry if "href" in entry else {
                    "text": entry["section"], "href": entry["contents"][0]["href"].split("#")[0]}

            for index, entry in enumerate(contents):
                children = entry.get("contents", [])
                if children and ("section" in children[0] or children[0].get("href") in title_only):
                    entry["contents"] = [page_link(child) for child in children]
                else:
                    contents[index] = page_link(entry)
            save_membership(membership, contents)
    for name, data in {"_quarto.yml": (json.dumps(SITE_CONFIG, indent=2) + "\n").encode(),
                       "site.css": (ASSET_ROOT / "site.css").read_bytes()}.items():
        if not (root / name).exists():
            atomic_write(root / name, data)
    ignore = root / ".gitignore"
    existing = ignore.read_bytes() if ignore.exists() else b""
    missing = [line.encode() for line in IGNORES if line.encode() not in existing.splitlines()]
    if missing:
        prefix = existing + (b"\n" if existing and not existing.endswith(b"\n") else b"")
        atomic_write(ignore, prefix + b"\n".join(missing) + b"\n")
    for name, data in tooling.items():
        atomic_write(root / name, data, 0o755)
    for path in retired:
        path.unlink()


def include(membership: Path, state: dict, page: str, title: str, group: str | None) -> None:
    if not title.strip() or (group is not None and not group.strip()):
        raise ValueError("expected a nonempty title and group name")
    contents = state["website"]["sidebar"]["contents"]
    target = contents
    if group:
        section = next((entry for entry in contents if entry.get("section") == group), None)
        if section is None:
            section = {"section": group, "contents": []}
            contents.append(section)
        target = section["contents"]
    position = len(target)
    for siblings in [contents, *(entry["contents"] for entry in contents if "contents" in entry)]:
        for index, entry in enumerate(siblings):
            if entry.get("href") == page:
                siblings.pop(index)
                if siblings is target:
                    position = index
                break
    target.insert(position, {"text": title, "href": page})
    contents[:] = [entry for entry in contents if entry.get("contents", [entry])]
    save_membership(membership, contents)


def refresh(root: Path, page: str) -> None:
    directory = (root / page).parent
    if (directory / "Snakefile").is_file():
        subprocess.run(["snakemake", "--cores", "1", "--allowed-rules", "present", "--", "present"],
                       cwd=directory, check=True)
    for target in (page, "index.qmd"):
        subprocess.run(["bash", "render.sh", f"./{target}"], cwd=root, check=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("init", "include", "refresh"):
        command = commands.add_parser(name)
        command.add_argument("root", type=Path)
        if name != "init":
            command.add_argument("page", type=Path)
        if name == "include":
            command.add_argument("--title", required=True)
            command.add_argument("--group", help="optional sidebar group")
    args = parser.parse_args()
    try:
        root = args.root.resolve()
        if args.command == "init":
            init(root)
            return
        page = args.page.resolve().relative_to(root).as_posix()
        if page == "index.qmd" or not re.fullmatch(r"[A-Za-z0-9._/-]+\.qmd", page) or not args.page.read_bytes().strip():
            raise ValueError(f"{args.page}: expected a populated report QMD below the site root")
        membership = root / MEMBERSHIP
        state = json.loads(membership.read_bytes())
        if args.command == "include":
            include(membership, state, page, args.title, args.group)
        elif page in state["project"]["render"]:
            refresh(root, page)
        else:
            raise ValueError(f"{page}: include the report before refreshing it")
    except subprocess.CalledProcessError as exc:
        parser.exit(exc.returncode, f"manuscript failed: {exc}\n")
    except (OSError, ValueError, KeyError, TypeError, IndexError) as exc:
        parser.exit(1, f"manuscript failed: {exc}\n")


if __name__ == "__main__":
    main()
