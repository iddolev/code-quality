#!/usr/bin/env python3
"""
Install / update the Code Quality suite in the current project folder.

Usage:
    python code_quality_install.py [--target FOLDER] [--dry-run] [--yes] [--force] [--help]

Place this script in your project root and run it from there.

TODO: If a future Code Quality version removes a file that existed in a previous version,
      the installer won't delete it from the user's project.
      Consider tracking installed files in .code-quality or a manifest.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.request import urlopen
from urllib.error import URLError

import yaml


# Although the following 3 variables appear in dist/.claude/scripts/code-quality/common.py
# this file cannot be accessed here, as it can be copied only during copy_path_map()
CQ_FOLDER = ".code-quality"
CQ_CONFIG_FOLDER = f"{CQ_FOLDER}/config"
CQ_INFO_FILENAME = ".cq.yaml"
CQ_INFO_FILEPATH = f"{CQ_CONFIG_FOLDER}/{CQ_INFO_FILENAME}"
CQ_VERSION_FILEPATH = f"{CQ_FOLDER}/version.yaml"

CQ_DISTRIBUTION_FOLDER = "distribute"
CQ_VERSION_FILEPATH_REMOTE = f"{CQ_DISTRIBUTION_FOLDER}/{CQ_FOLDER}/version.yaml"


REPO_URL = "https://github.com/iddolev/code-quality.git"
REPO_SLUG = "iddolev/code-quality"  # for raw.githubusercontent.com
# TODO: support cloning a specific tag/branch, not only HEAD

# List of:
# (source path in cloned repo, destination relative to project root, overwrite).
# When overwrite is True, the destination is always replaced with the repo version.
# When overwrite is False, the file is only copied on first install (i.e. when the
# destination does not yet exist).
# Directories are copied recursively; files are copied individually.
PATH_MAP: list[tuple[str, str, bool]] = [
    (f"{CQ_VERSION_FILEPATH_REMOTE}",               CQ_VERSION_FILEPATH, True),
    (".claude/commands/code-quality/", ".claude/commands/code-quality/", True),
    (".claude/code-quality",                    ".claude/code-quality/", True),
]

# The following are supposed to be copied as-is to the user's project
# and therefore should not also be pushed to the user's project repo.
GITIGNORE_ENTRIES = [
    "code_quality_install.bat",
    f"{CQ_FOLDER}/installation/",
    ".claude/commands/code-quality/",
    ".claude/code-quality/",
]


def warn(*args, **kwargs) -> None:
    """Print to stderr."""
    print(*args, file=sys.stderr, **kwargs)


# ── Core logic ───────────────────────────────────────────────────────────────


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Install / update the CQ framework into the current project folder.",
    )
    p.add_argument("--target", type=Path, default=None,
                   help="Install into FOLDER instead of the current directory.")
    # For dry-run, we cannot skip clone,
    # because we want the entire logic to run and inspect all repo files
    # and say what would be done in a real run.
    p.add_argument("--dry-run", action="store_true",
                   help="Show what would be done without touching any files. "
                        "Note: still clones the repo to inspect its contents.")
    p.add_argument("--yes", "-y", action="store_true",
                   help="Skip the confirmation prompt.")
    p.add_argument("--force", action="store_true",
                   help="Reinstall even if already at the latest version.")
    p.add_argument("--version", action="store_true",
                   help="Show the currently installed Code Quality suite version and exit.")
    return p.parse_args()


def clone_repo(tmp_dir: Path) -> Path:
    """Clone the Code Quality repo into *tmp_dir* and return the path."""
    dest = tmp_dir / "code_quality"
    print(f"⏳ Cloning {REPO_URL} ...")
    try:
        subprocess.run(
            [
                "git", "clone",
                # --depth=1 means shallow clone — we only need the latest files, not history
                "--depth", "1",
                REPO_URL,
                str(dest),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        warn("❌ git is not installed or not on PATH. Please install git and try again.")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        warn(f"❌ Failed to clone repository (check your network connection):\n{e.stderr}")
        sys.exit(1)
    print("✅ Done.")
    return dest


def read_cq_version(path: Path) -> str:
    """Read the version field from a YAML .cq file."""
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, UnicodeDecodeError) as e:
        raise ValueError(f"Cannot read {path}: {e}") from e
    except yaml.YAMLError as e:
        raise ValueError(f"Cannot parse {path}: {e}") from e
    value = data.get('version')
    if value:
        return str(value)
    raise ValueError(f"{path} is missing a 'version' field")


def fetch_remote_version() -> str:
    """Fetch version.yaml from remote repo and return version"""
    try:
        url = f"https://raw.githubusercontent.com/{REPO_SLUG}/main/{CQ_VERSION_FILEPATH_REMOTE}"
        with urlopen(url, timeout=10) as resp:
            data = yaml.safe_load(resp.read().decode()) or {}
    except (URLError, UnicodeDecodeError, yaml.YAMLError) as e:
        raise ValueError("Could not fetch remote version from GitHub (check network)") from e
    if v := data.get("version"):
        return v
    raise ValueError(f"Remote {CQ_VERSION_FILEPATH_REMOTE} is missing a 'version' field")


def copy_file(src: Path, dest: Path, *, overwrite: bool, dry_run: bool) -> None:
    """Copy a single file from *src* to *dest*. Skips if dest exists and overwrite is False."""
    if not overwrite and dest.exists():
        print(f"  ⏭️  Already exists, skipping: {dest}")
        return
    if dry_run:
        print(f"  [dry-run] Would copy {src.name} → {dest}")
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)


def copy_entry(src: Path, dest: Path, *, overwrite: bool, dry_run: bool) -> None:
    """Process a path from PATH_MAP. For directories, rglob finds all files
    at every depth; parent dirs are created on demand by copy_file."""
    if src.is_dir():
        for descendant in sorted(src.rglob("*")):
            if descendant.is_file():
                rel = descendant.relative_to(src)
                copy_file(descendant, dest / rel, overwrite=overwrite, dry_run=dry_run)
    else:
        copy_file(src, dest, overwrite=overwrite, dry_run=dry_run)
    print(f"  📄 Copied → {dest}")


def _is_cq_repo(project_dir: Path) -> bool:
    """Detect if *project_dir* is the Code Quality repo itself.
    (This is a bit fragile, in case we ever rename code_quality_install.py
    or move it to a different folder,
    but that change would be rare, so that's good enough for now.
    """
    return (project_dir / "installation" / "code_quality_install.py").exists()


GIT_IGNORE_COMMENT = "# Don't include files of Code Quality in your repo"


def update_gitignore(project_dir: Path, *, dry_run: bool) -> None:
    """Create or update .gitignore with GITIGNORE_ENTRIES entries."""
    gitignore_path = project_dir / ".gitignore"

    new_section = f"{GIT_IGNORE_COMMENT}\n" + "\n".join(GITIGNORE_ENTRIES) + "\n"

    if not gitignore_path.exists():
        if dry_run:
            print("  [dry-run] Would create .gitignore with Code Quality entries")
            return
        gitignore_path.write_text(new_section, encoding="utf-8")
        print("  📄 Created .gitignore")
        return

    content = gitignore_path.read_text(encoding="utf-8")
    content_lines = content.splitlines()

    content_stripped = {line.strip() for line in content_lines}
    git_ignore_s = {e.strip() for e in GITIGNORE_ENTRIES}
    existing_ignore = [line for line in content_lines if line.strip() in git_ignore_s]
    missing = [e for e in GITIGNORE_ENTRIES if e.strip() not in content_stripped]

    if not existing_ignore:
        # None of the GITIGNORE_ENTRIES lines exist — add full section
        if dry_run:
            print("  [dry-run] Would add Code Quality section to .gitignore")
            return
        gitignore_path.write_text(content.rstrip() + "\n\n" + new_section, encoding="utf-8")
        print("  📄 Updated .gitignore")
        return

    if not missing:
        return

    # Find last occurrence of any GITIGNORE_ENTRIES line
    last_idx = -1
    for i, line in enumerate(content_lines):
        if line.strip() in git_ignore_s:
            last_idx = i

    if dry_run:
        print("  [dry-run] Would add some Code Quality entries to .gitignore")
        return

    new_lines = content_lines[: last_idx + 1] + missing + content_lines[last_idx + 1:]
    gitignore_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    print("  📄 Updated .gitignore")


_VERSION_RE = re.compile(r"^version\s*:")


def update_cq_version(project_dir: Path, new_version: str, *, dry_run: bool) -> None:
    """Update the version line in the project's version.yaml, preserving comments and formatting."""
    version_path = project_dir / CQ_VERSION_FILEPATH
    if not version_path.exists():
        raise FileNotFoundError(f"Missing file: {version_path}")
    try:
        content = version_path.read_text(encoding="utf-8")
    except OSError as e:
        warn(f"  ⚠️  Could not read {CQ_VERSION_FILEPATH}: {e}")
        return

    lines = content.splitlines(keepends=True)
    for i, line in enumerate(lines):
        if _VERSION_RE.match(line):
            new_line = f"version: {new_version}\n"
            if lines[i] == new_line:
                return
            lines[i] = new_line
            break
    else:
        return
    if dry_run:
        print(f"  [dry-run] Would update version to {new_version} in {CQ_VERSION_FILEPATH}")
    else:
        print(f"  📄 Updated version to {new_version} in {CQ_VERSION_FILEPATH}")
        try:
            version_path.write_text("".join(lines), encoding="utf-8")
        except OSError as e:
            warn(f"  ⚠️  Could not update version in {CQ_VERSION_FILEPATH}: {e}")


def copy_path_map(repo_dir: Path, project_dir: Path, *, dry_run: bool) -> None:
    """Walk PATH_MAP and copy every framework file into the project."""
    failed: list[tuple[str, str]] = []
    for src_rel, dest_rel, overwrite in PATH_MAP:
        src = repo_dir / src_rel
        dest = project_dir / dest_rel
        if not src.exists():
            warn(f"  ⚠️  Source not found in repo: {src_rel} — skipping")
            continue
        try:
            copy_entry(src, dest, overwrite=overwrite, dry_run=dry_run)
        except OSError as e:
            warn(f"  ❌ Failed to copy {src_rel} → {dest_rel}: {e}")
            failed.append((src_rel, dest_rel))
    if failed:
        warn(f"\n⚠️  {len(failed)} path(s) failed to copy. "
             "The installation is incomplete — some files may be outdated or missing.")


CQ_CLAUDE_SECTION_HEADING = "## CLAUDE instructions specific to Code Quality"


def install(repo_dir: Path, project_dir: Path, new_version: str, *, dry_run: bool) -> None:
    """Install Code Quality SUITE files into the project."""
    print(f"\n📦 Installing Code Quality v{new_version} into {project_dir}\n")
    copy_path_map(repo_dir, project_dir, dry_run=dry_run)
    update_gitignore(project_dir, dry_run=dry_run)
    update_cq_version(project_dir, new_version, dry_run=dry_run)


def resolve_versions(project_dir: Path, *, force: bool) -> tuple[str | None, str]:
    """Fetch the remote version and read the local one (if installed).

    Returns (current_version, new_version).
    Exits early if already up to date (unless *force* is set).
    """
    print("⏳ Checking latest version...")
    try:
        new_version = fetch_remote_version()
    except ValueError as e:
        warn(f"❌ {e}")
        sys.exit(1)
    print(f"   Latest: v{new_version}")

    current_version = None
    version_path = project_dir / CQ_VERSION_FILEPATH
    if version_path.exists():
        try:
            current_version = read_cq_version(version_path)
        except ValueError as e:
            warn(f"⚠️  {e}")
            warn("   Ignoring version.yaml and proceeding as a fresh install.")

    if current_version == new_version and not force:
        print(f"ℹ️  Already at version {new_version}.)")
        print("    You can use --force to reinstall.")
        sys.exit(0)

    return current_version, new_version


def confirm_install(current_version: str | None, new_version: str,
                    project_dir: Path) -> bool:
    """Prompt the user and return True to proceed, False to abort."""
    if current_version:
        prompt = ("This will update Code Quality "
                  f"(v{current_version} → v{new_version}) in {project_dir}")
    else:
        prompt = f"This will install Code Quality v{new_version} in {project_dir}"
    print(prompt)
    try:
        answer = input("Continue? [Y/n] ").strip().lower()
        return answer in ("y", "yes", "")
    except (KeyboardInterrupt, EOFError):
        print()
        return False


def print_version_info(project_dir: Path) -> None:
    """Print installed and latest Code Quality versions, then exit."""
    version_path = project_dir / CQ_VERSION_FILEPATH
    if version_path.exists():
        try:
            local = read_cq_version(version_path)
            print(f"Installed: v{local}")
        except ValueError as e:
            warn(f"❌ {e}")
            sys.exit(1)
    else:
        print("Installed: (not installed)")
    try:
        remote = fetch_remote_version()
        print(f"Latest:    v{remote}")
    except ValueError:
        print("Latest:    (unable to fetch)")


def main() -> None:
    args = parse_args()
    project_dir = args.target.resolve() if args.target else Path.cwd()
    if not project_dir.is_dir():
        warn(f"❌ Target directory does not exist: {project_dir}")
        sys.exit(1)

    # --version: show installed and latest versions, then exit.
    if args.version:
        print_version_info(project_dir)
        return

    if _is_cq_repo(project_dir):
        warn("❌ Refusing to install — target directory is the Code Quality repo itself.")
        sys.exit(1)

    current_version, new_version = resolve_versions(project_dir, force=args.force)

    if not args.dry_run and not args.yes:
        if not confirm_install(current_version, new_version, project_dir):
            print("Aborted.")
            return

    with tempfile.TemporaryDirectory(prefix="code-quality-") as tmp:
        tmp_dir = Path(tmp)
        repo_dir = clone_repo(tmp_dir)
        install(repo_dir, project_dir, new_version, dry_run=args.dry_run)

    if args.dry_run:
        print("\n🏁 Dry run complete — no files were modified.")
    else:
        print()
        print(f"🏁 Code Quality v{new_version} installed successfully.")
        warn(f"⚠️ IMPORTANT NOTE: You should commit {CQ_VERSION_FILEPATH} to your repo, "
             "to remember the relevant Code Quality info.")


if __name__ == "__main__":
    main()
