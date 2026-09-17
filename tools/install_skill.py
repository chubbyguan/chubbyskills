#!/usr/bin/env python3
"""Copy portable Agent Skills, including their repository-local dependencies.

This only installs source files. It never installs Python packages or replaces an
existing skill. The resulting skill directories can be moved independently.
"""

import argparse
import json
import re
import shutil
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMMON_SKILLS = {
    "bilibili-transcribe", "content-enrich", "douyin-transcribe",
    "learning-notes-automation", "tiktok-transcribe", "weibo-transcribe",
    "xiaohongshu-ingest", "youtube-transcribe", "zhihu-transcribe",
}
SUPPORTED_SKILLS = COMMON_SKILLS | {
    "industry-intelligence-radar", "knowledge-base-management",
    "podcast-transcribe", "wechat-article-ingest", "x-ingest",
}
IGNORED_NAMES = {
    ".git", ".venv", "venv", "__pycache__", ".pytest_cache", ".ruff_cache",
    ".DS_Store", ".chubby", "output", "outputs", "runs",
}


def ignored(name):
    return name in IGNORED_NAMES or name.startswith(".env") or name.endswith((".pyc", ".pyo"))


def payload_files(source):
    """Reject links instead of copying files from outside the source tree."""
    if source.is_symlink():
        raise ValueError(f"Symlink source is not supported: {source}")
    if source.is_file():
        return [(source, Path(source.name))]
    if not source.is_dir():
        raise ValueError(f"Missing source: {source}")
    result = []
    for child in sorted(source.iterdir()):
        if ignored(child.name):
            continue
        if child.is_symlink():
            raise ValueError(f"Symlink source is not supported: {child}")
        if child.is_dir():
            result.extend((path, Path(child.name) / rel) for path, rel in payload_files(child))
        elif child.is_file():
            result.append((child, Path(child.name)))
        else:
            raise ValueError(f"Unsupported source file: {child}")
    return result


def skill_payload(name, repo_root):
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", name) or name not in SUPPORTED_SKILLS:
        raise ValueError(f"Unknown skill: {name}")
    skill = repo_root / name
    if not (skill / "SKILL.md").is_file():
        raise ValueError(f"Missing SKILL.md: {skill}")
    files = payload_files(skill)
    if name in COMMON_SKILLS:
        files.extend((path, Path("chubby_common") / rel) for path, rel in payload_files(repo_root / "chubby_common"))
    if name == "knowledge-base-management":
        for module in ("vault_index.py", "vault_curator.py", "evidence_brief.py"):
            files.extend((path, Path("tools") / rel) for path, rel in payload_files(repo_root / "tools" / module))
    if not (skill / "LICENSE").exists():
        files.extend(payload_files(repo_root / "LICENSE"))
    return files


def install_skills(names, destination, repo_root=ROOT):
    """Validate all inputs before copying; never merge into an existing skill."""
    repo_root = Path(repo_root).resolve()
    destination = Path(destination).expanduser()
    if destination.is_symlink():
        raise ValueError(f"Destination must not be a symlink: {destination}")
    destination = destination.resolve()
    names = list(dict.fromkeys(names))
    if not names:
        raise ValueError("Select at least one skill")
    plans = {}
    for name in names:
        files = skill_payload(name, repo_root)
        target = destination / name
        if target.exists() or target.is_symlink():
            raise FileExistsError(f"Skill already exists; nothing overwritten: {target}")
        for source_root in (repo_root / name, repo_root / "chubby_common", repo_root / "tools"):
            if destination == source_root or source_root in destination.parents:
                raise ValueError(f"Destination is inside a source directory: {destination}")
        plans[name] = files

    version = (repo_root / "VERSION").read_text(encoding="utf-8").strip()
    destination.mkdir(parents=True, exist_ok=True)
    installed = []
    with tempfile.TemporaryDirectory(prefix=".chubby-install-", dir=destination) as temporary:
        staging = Path(temporary)
        for name, files in plans.items():
            skill_stage = staging / name
            skill_stage.mkdir()
            for source, relative in files:
                target = skill_stage / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
            manifest = {"skill": name, "version": version, "files": sorted(str(relative) for _, relative in files)}
            (skill_stage / "installation.json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
        try:
            for name in names:
                target = destination / name
                # Exclusive creation also catches a target created since preflight.
                target.mkdir()
                installed.append(target)
                shutil.copytree(staging / name, target, dirs_exist_ok=True)
        except Exception:
            for target in installed:
                shutil.rmtree(target)
            raise
    return installed


def main(argv=None):
    parser = argparse.ArgumentParser(description="Install portable skills with bundled local dependencies")
    parser.add_argument("skills", nargs="*", help="Full skill directory names (use --list to see them)")
    parser.add_argument("--all", action="store_true", help="Install all supported skills")
    parser.add_argument("--dest", help="Agent skills directory; no existing skill is overwritten")
    parser.add_argument("--list", action="store_true", help="List supported skill names")
    args = parser.parse_args(argv)
    if args.list:
        print("\n".join(sorted(SUPPORTED_SKILLS)))
        return 0
    if args.all and args.skills:
        parser.error("Use skill names or --all, not both")
    if not args.dest or (not args.all and not args.skills):
        parser.error("Select skill names or --all and provide --dest")
    try:
        installed = install_skills(sorted(SUPPORTED_SKILLS) if args.all else args.skills, args.dest)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"Installation failed: {exc}\n")
    for path in installed:
        print(f"Installed {path.name}: {path}")
    print("Source files installed. Install optional runtime dependencies separately with setup.sh.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
