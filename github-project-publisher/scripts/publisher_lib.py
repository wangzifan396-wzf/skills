from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence


MAX_GITHUB_FILE_BYTES = 100 * 1024 * 1024
VERSION_PATTERN = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)(?:[-+][0-9A-Za-z.-]+)?$")
GITHUB_HTTPS = re.compile(r"^https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$")
GITHUB_SSH = re.compile(r"^git@github\.com:([^/]+)/([^/]+?)(?:\.git)?/?$")
PRIVATE_KEY_PATTERN = re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----")
SECRET_ASSIGNMENT_PATTERN = re.compile(
    r"(?im)(?:api[_-]?key|access[_-]?token|secret|password|private[_-]?key)\s*[:=]\s*['\"][^'\"]{8,}['\"]"
)
SENSITIVE_NAMES = (
    ".env",
    ".pem",
    ".key",
    ".p12",
    ".pfx",
    ".kdbx",
    "id_rsa",
    "id_ed25519",
    "credentials.json",
)


class PublisherError(RuntimeError):
    pass


@dataclass(frozen=True)
class Finding:
    severity: str
    path: str
    rule: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {
            "severity": self.severity,
            "path": self.path,
            "rule": self.rule,
            "message": self.message,
        }


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def run_command(
    args: Sequence[str],
    cwd: Path | None = None,
    *,
    check: bool = True,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        list(args),
        cwd=str(cwd) if cwd else None,
        env={**os.environ, **(env or {})},
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    if check and result.returncode != 0:
        command = " ".join(args)
        detail = (result.stderr or result.stdout).strip()
        raise PublisherError(f"Command failed ({result.returncode}): {command}\n{detail}")
    return result


def git(project: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return run_command(["git", *args], project, check=check)


def require_git_project(project_value: str | Path) -> Path:
    project = Path(project_value).expanduser().resolve()
    if not project.is_dir():
        raise PublisherError(f"Project directory does not exist: {project}")
    result = git(project, "rev-parse", "--show-toplevel", check=False)
    if result.returncode != 0:
        raise PublisherError(f"Project is not a Git repository: {project}")
    root = Path(result.stdout.strip()).resolve()
    if root != project:
        raise PublisherError(f"Project must be the Git root, not a subdirectory: {root}")
    return root


def parse_github_slug(remote: str) -> str | None:
    value = remote.strip()
    match = GITHUB_HTTPS.match(value) or GITHUB_SSH.match(value)
    if not match:
        return None
    owner, repository = match.groups()
    if not owner or not repository or owner in {".", ".."} or repository in {".", ".."}:
        return None
    return f"{owner}/{repository}"


def normalize_version(value: str) -> str:
    version = value.strip()
    if not VERSION_PATTERN.match(version):
        raise PublisherError(
            "Version must look like v1.2.3 or 1.2.3, with optional prerelease/build suffix"
        )
    return version if version.startswith("v") else f"v{version}"


def detect_version(project: Path, explicit: str | None = None) -> tuple[str | None, str | None]:
    if explicit:
        return normalize_version(explicit), "argument"
    package = project / "package.json"
    if package.is_file():
        try:
            data = json.loads(package.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise PublisherError(f"Unable to read package.json: {error}") from error
        if isinstance(data.get("version"), str) and data["version"].strip():
            return normalize_version(data["version"]), "package.json"
    for filename in ("pyproject.toml", "Cargo.toml"):
        target = project / filename
        if target.is_file():
            content = target.read_text(encoding="utf-8", errors="replace")
            match = re.search(r"(?m)^\s*version\s*=\s*[\"']([^\"']+)[\"']", content)
            if match:
                return normalize_version(match.group(1)), filename
    return None, None


def list_candidates(project: Path) -> list[str]:
    result = git(project, "ls-files", "--cached", "--others", "--exclude-standard", "-z")
    values = [item for item in result.stdout.split("\x00") if item]
    return sorted(set(values), key=str.casefold)


def file_is_sensitive_name(relative: str) -> bool:
    path = Path(relative)
    name = path.name.lower()
    if name == ".env.example" or name.startswith(".env."):
        return False
    return name in SENSITIVE_NAMES or any(name.endswith(suffix) for suffix in SENSITIVE_NAMES if suffix.startswith("."))


def inspect_candidate(project: Path, relative: str) -> list[Finding]:
    target = project / relative
    findings: list[Finding] = []
    if not target.is_file():
        return findings
    if file_is_sensitive_name(relative):
        findings.append(Finding("blocker", relative, "sensitive-name", "Sensitive credential-like filename"))
    size = target.stat().st_size
    if size > MAX_GITHUB_FILE_BYTES:
        findings.append(Finding("blocker", relative, "large-file", "File exceeds GitHub's 100 MiB limit"))
    if size > 2 * 1024 * 1024:
        return findings
    try:
        text = target.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return findings
    if PRIVATE_KEY_PATTERN.search(text):
        findings.append(Finding("blocker", relative, "private-key", "Private key material detected"))
    if SECRET_ASSIGNMENT_PATTERN.search(text):
        findings.append(Finding("blocker", relative, "secret-assignment", "Credential-like assignment detected"))
    return findings


def inspect_project(project: Path) -> dict:
    candidates = list_candidates(project)
    findings = [finding for relative in candidates for finding in inspect_candidate(project, relative)]
    status = git(project, "status", "--short", "--branch").stdout.splitlines()
    branch = git(project, "branch", "--show-current").stdout.strip() or "HEAD"
    head = git(project, "rev-parse", "HEAD").stdout.strip()
    remotes = []
    for line in git(project, "remote", "-v").stdout.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[2] == "(fetch)":
            remotes.append({"name": parts[0], "url": parts[1]})
    candidate_bytes = sum((project / relative).stat().st_size for relative in candidates if (project / relative).is_file())
    return {
        "project": str(project),
        "branch": branch,
        "head": head,
        "status": status,
        "candidateFiles": len(candidates),
        "candidateBytes": candidate_bytes,
        "candidates": candidates,
        "remotes": remotes,
        "findings": [finding.as_dict() for finding in findings],
        "blockers": [finding.as_dict() for finding in findings if finding.severity == "blocker"],
        "warnings": [finding.as_dict() for finding in findings if finding.severity == "warning"],
        "readiness": {
            "readme": any((project / name).is_file() for name in ("README", "README.md", "README.rst")),
            "license": any((project / name).is_file() for name in ("LICENSE", "LICENSE.md", "LICENSE.txt")),
            "gitignore": (project / ".gitignore").is_file(),
        },
    }


def remote_inspect(remote: str, branch: str) -> dict:
    result = run_command(["git", "ls-remote", "--heads", remote, branch], check=False)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise PublisherError(f"Unable to inspect remote {remote}: {detail}")
    heads = []
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) == 2:
            heads.append({"sha": parts[0], "ref": parts[1]})
    return {
        "remote": remote,
        "branch": branch,
        "heads": heads,
        "empty": not heads,
        "sha": heads[0]["sha"] if heads else None,
    }


def local_tags(project: Path) -> list[str]:
    return [line.strip() for line in git(project, "tag", "--list", "v*").stdout.splitlines() if line.strip()]


def previous_tag(project: Path, current_tag: str | None) -> str | None:
    tags = local_tags(project)
    if not tags:
        return None
    ordered = sorted(tags, reverse=True)
    for tag in ordered:
        if tag != current_tag:
            return tag
    return None


def release_notes(project: Path, tag: str, title: str | None = None, previous: str | None = None) -> str:
    range_value = f"{previous}..HEAD" if previous else "-20"
    if previous:
        output = git(project, "log", "--no-merges", "--pretty=format:- %s (%h)", range_value).stdout.strip()
    else:
        output = git(project, "log", "--no-merges", "-20", "--pretty=format:- %s (%h)").stdout.strip()
    heading = title or f"Release {tag}"
    body = output or "- No commit summary was available."
    return f"# {heading}\n\nGenerated from verified Git history.\n\n{body}\n"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def create_source_archive(project: Path, output_dir: Path, tag: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    archive = output_dir / f"{project.name}-{tag}.zip"
    run_command(["git", "archive", "--format=zip", f"--prefix={project.name}-{tag}/", "--output", str(archive), "HEAD"], project)
    return archive


def copy_assets(project: Path, output_dir: Path, assets: Iterable[str]) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    copied: list[Path] = []
    for value in assets:
        source = Path(value).expanduser()
        if not source.is_absolute():
            source = (project / source).resolve()
        else:
            source = source.resolve()
        if not source.is_file():
            raise PublisherError(f"Release asset does not exist: {source}")
        if source.stat().st_size > MAX_GITHUB_FILE_BYTES:
            raise PublisherError(f"Release asset exceeds GitHub's 100 MiB limit: {source}")
        target = output_dir / source.name
        if target.exists() and target.resolve() != source:
            raise PublisherError(f"Release asset filename collision: {target.name}")
        if target.resolve() != source:
            shutil.copy2(source, target)
        copied.append(target)
    return copied


def write_checksums(artifacts: Iterable[Path], output_dir: Path) -> Path:
    checksum = output_dir / "SHA256SUMS.txt"
    lines = [f"{sha256_file(path)}  {path.name}" for path in sorted(artifacts, key=lambda item: item.name)]
    checksum.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return checksum


def ensure_remote(project: Path, remote_name: str, remote_url: str, execute: bool) -> str:
    existing = git(project, "remote", "get-url", remote_name, check=False)
    if existing.returncode == 0:
        current = existing.stdout.strip()
        same_github = parse_github_slug(current) is not None and parse_github_slug(current) == parse_github_slug(remote_url)
        if current != remote_url and not same_github:
            raise PublisherError(
                f"Remote '{remote_name}' already points to a different URL; refusing to rewrite it: {current}"
            )
        return "existing"
    if execute:
        git(project, "remote", "add", remote_name, remote_url)
    return "add"


def require_fast_forward(project: Path, remote_name: str, branch: str, remote_audit: dict, allow_existing: bool) -> None:
    if remote_audit["empty"]:
        return
    if not allow_existing:
        raise PublisherError("Remote branch is non-empty; pass --allow-existing only after confirming same history")
    fetch = git(project, "fetch", remote_name, branch, check=False)
    if fetch.returncode != 0:
        raise PublisherError(f"Unable to fetch existing remote branch: {fetch.stderr.strip()}")
    check = git(project, "merge-base", "--is-ancestor", f"{remote_name}/{branch}", "HEAD", check=False)
    if check.returncode != 0:
        raise PublisherError("Remote branch is not an ancestor of local HEAD; refusing non-fast-forward publish")


def push_branch(project: Path, remote_name: str, branch: str) -> None:
    git(project, "push", "--set-upstream", remote_name, f"HEAD:refs/heads/{branch}")


def tag_exists_remote(remote: str, tag: str) -> bool:
    result = run_command(["git", "ls-remote", "--tags", remote, f"refs/tags/{tag}"], check=False)
    if result.returncode != 0:
        raise PublisherError(f"Unable to inspect remote tag {tag}: {result.stderr.strip()}")
    return bool(result.stdout.strip())


def create_and_push_tag(project: Path, remote_name: str, remote_url: str, tag: str, execute: bool) -> str:
    if tag in local_tags(project) or tag_exists_remote(remote_url, tag):
        raise PublisherError(f"Tag already exists locally or remotely: {tag}")
    if execute:
        git(project, "tag", "-a", tag, "-m", f"Release {tag}")
        git(project, "push", remote_name, f"refs/tags/{tag}")
    return "created"


def gh_command() -> str:
    candidate = os.environ.get("GH_BIN", "gh")
    if shutil.which(candidate) is None and not Path(candidate).is_file():
        raise PublisherError("GitHub CLI 'gh' was not found; install it or set GH_BIN")
    return candidate


def create_github_release(
    slug: str,
    tag: str,
    title: str,
    notes_file: Path,
    artifacts: list[Path],
    execute: bool,
) -> dict:
    command = os.environ.get("GH_BIN", "gh")
    args = [command, "release", "create", tag, "--repo", slug, "--title", title, "--notes-file", str(notes_file)]
    args.extend(str(path) for path in artifacts)
    if not execute:
        return {"status": "planned", "command": args}
    gh_command()
    result = run_command(args)
    return {"status": "created", "stdout": result.stdout.strip()}


def verify_github_release(slug: str, tag: str, expected_assets: Iterable[Path]) -> dict:
    command = gh_command()
    result = run_command([
        command,
        "release",
        "view",
        tag,
        "--repo",
        slug,
        "--json",
        "tagName,url,assets",
    ])
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise PublisherError(f"GitHub CLI returned invalid Release JSON: {error}") from error
    actual = {item.get("name") for item in payload.get("assets", []) if item.get("name")}
    expected = {path.name for path in expected_assets}
    return {
        "tagName": payload.get("tagName"),
        "url": payload.get("url"),
        "assets": sorted(actual),
        "expectedAssets": sorted(expected),
        "assetsMatch": expected.issubset(actual),
    }


def verify_remote(project: Path, remote_url: str, branch: str, tag: str | None = None) -> dict:
    local_head = git(project, "rev-parse", "HEAD").stdout.strip()
    branch_audit = remote_inspect(remote_url, branch)
    result = {
        "localHead": local_head,
        "remoteBranch": branch_audit.get("sha"),
        "branchMatches": local_head == branch_audit.get("sha"),
        "tag": tag,
        "tagMatches": None,
    }
    if tag:
        tag_result = run_command(["git", "ls-remote", "--tags", remote_url, f"refs/tags/{tag}"], check=False)
        if tag_result.returncode != 0:
            raise PublisherError(f"Unable to verify remote tag {tag}: {tag_result.stderr.strip()}")
        tag_sha = tag_result.stdout.split()[0] if tag_result.stdout.split() else None
        result["remoteTag"] = tag_sha
        result["tagMatches"] = bool(tag_sha)
    result["verified"] = bool(result["branchMatches"] and (result["tagMatches"] is not False))
    return result


def json_dump(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
