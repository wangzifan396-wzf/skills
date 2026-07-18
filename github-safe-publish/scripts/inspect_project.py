from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

from publish_lib import (
    PublishError,
    decoded,
    git_has_head,
    git_lines,
    git_root,
    git_text,
    null_split,
    run_git,
    utc_now,
    write_json,
)


GITHUB_MAX_FILE_BYTES = 100 * 1024 * 1024
LARGE_FILE_WARNING_BYTES = 50 * 1024 * 1024
CONTENT_SCAN_LIMIT = 2 * 1024 * 1024

DEFAULT_IGNORED_DIRECTORIES = {
    ".git": "Git internal database",
    ".hg": "Mercurial internal database",
    ".svn": "Subversion internal database",
    "node_modules": "installed Node dependencies",
    ".venv": "Python virtual environment",
    "venv": "Python virtual environment",
    "env": "Python virtual environment",
    "__pycache__": "Python bytecode cache",
    ".pytest_cache": "pytest cache",
    ".mypy_cache": "mypy cache",
    ".ruff_cache": "Ruff cache",
    ".tox": "tox environments",
    ".nox": "nox environments",
    ".cache": "tool cache",
    ".idea": "IDE-local metadata",
    ".vs": "Visual Studio local metadata",
}

DEFAULT_IGNORED_FILES = {
    ".DS_Store": "macOS metadata",
    "Thumbs.db": "Windows thumbnail cache",
    ".coverage": "coverage data",
    "coverage.xml": "coverage report",
}

DEFAULT_IGNORED_GLOBS = {
    "*.pyc": "Python bytecode",
    "*.pyo": "Python bytecode",
    "*.log": "runtime log",
    "*.tmp": "temporary file",
    "*.temp": "temporary file",
    "*.swp": "editor swap file",
    "*.swo": "editor swap file",
    "npm-debug.log*": "package-manager error log",
    "yarn-error.log*": "package-manager error log",
    "pnpm-debug.log*": "package-manager error log",
}

SECRET_FILE_NAMES = {
    "id_rsa",
    "id_dsa",
    "id_ecdsa",
    "id_ed25519",
    "credentials.json",
    "service-account.json",
    ".netrc",
    ".pypirc",
}

SECRET_FILE_SUFFIXES = {".key", ".p12", ".pfx", ".jks", ".keystore"}
SAFE_ENV_SUFFIXES = (".example", ".sample", ".template", ".dist")

SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("private-key", re.compile(r"-----BEGIN (?:RSA |DSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("github-token", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b")),
    ("github-token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b")),
    ("aws-access-key", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("slack-token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b")),
    ("openai-key", re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b")),
]

ASSIGNMENT_PATTERN = re.compile(
    r"(?i)\b(?:password|passwd|client_secret|api[_-]?key|access[_-]?token|auth[_-]?token)\b"
    r"\s*[:=]\s*[\"']?(?P<value>[^\s\"'#;,]{8,})"
)

PLACEHOLDER_MARKERS = {
    "example",
    "sample",
    "dummy",
    "changeme",
    "change-me",
    "your_",
    "your-",
    "redacted",
    "placeholder",
    "not-a-real",
    "test-only",
    "xxxx",
    "${",
    "{{",
    "{",
    "<",
}


def posix(path: Path) -> str:
    return path.as_posix()


def finding(severity: str, code: str, path: str | None, message: str, **extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "severity": severity,
        "code": code,
        "path": path,
        "message": message,
    }
    payload.update(extra)
    return payload


def redact_remote_url(value: str) -> str:
    value = re.sub(r"(https://)[^/@\s]+@", r"\1[redacted]@", value)
    value = re.sub(r"(https://[^/:\s]+:)[^@\s]+@", r"\1[redacted]@", value)
    return value


def git_metadata(root: Path) -> dict[str, Any]:
    repo_root = git_root(root)
    if repo_root is None:
        return {
            "isRepository": False,
            "root": None,
            "hasHead": False,
            "branch": None,
            "status": [],
            "remotes": [],
        }
    if repo_root != root:
        raise PublishError(
            f"Project root must be the Git worktree root ({repo_root}); monorepo subdirectory publication "
            "requires a separate reviewed workflow"
        )

    branch_result = run_git(["symbolic-ref", "--quiet", "--short", "HEAD"], cwd=root, check=False)
    branch = decoded(branch_result.stdout) if branch_result.returncode == 0 else None
    status = git_lines(["status", "--short", "--branch"], cwd=root)
    remotes: list[dict[str, str]] = []
    for name in git_lines(["remote"], cwd=root):
        url_result = run_git(["remote", "get-url", name], cwd=root, check=False)
        if url_result.returncode == 0:
            remotes.append({"name": name, "url": redact_remote_url(decoded(url_result.stdout))})

    return {
        "isRepository": True,
        "root": str(root),
        "hasHead": git_has_head(root),
        "branch": branch,
        "status": status,
        "remotes": remotes,
    }


def read_gitignore_patterns(root: Path) -> list[str]:
    path = root / ".gitignore"
    if not path.is_file():
        return []
    patterns: list[str] = []
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if line and not line.startswith("#"):
            patterns.append(line)
    return patterns


def matches_ignore_pattern(relative: str, is_directory: bool, pattern: str) -> bool:
    negated = pattern.startswith("!")
    if negated:
        pattern = pattern[1:]
    pattern = pattern.replace("\\", "/")
    directory_only = pattern.endswith("/")
    pattern = pattern.rstrip("/")
    if not pattern or (directory_only and not is_directory):
        return False

    relative = relative.strip("/")
    path = PurePosixPath(relative)
    anchored = pattern.startswith("/")
    pattern = pattern.lstrip("/")
    if anchored:
        return fnmatch.fnmatchcase(relative, pattern) or relative.startswith(pattern + "/")
    if "/" in pattern:
        return path.match(pattern) or relative.startswith(pattern + "/")
    return any(fnmatch.fnmatchcase(part, pattern) for part in path.parts)


def ignored_by_patterns(relative: str, is_directory: bool, patterns: list[str]) -> bool:
    ignored = False
    for pattern in patterns:
        if matches_ignore_pattern(relative, is_directory, pattern):
            ignored = not pattern.startswith("!")
    return ignored


def default_exclusion(path: Path) -> str | None:
    for part in path.parts[:-1]:
        if part in DEFAULT_IGNORED_DIRECTORIES:
            return DEFAULT_IGNORED_DIRECTORIES[part]
    if path.name in DEFAULT_IGNORED_DIRECTORIES:
        return DEFAULT_IGNORED_DIRECTORIES[path.name]
    if path.name in DEFAULT_IGNORED_FILES:
        return DEFAULT_IGNORED_FILES[path.name]
    for pattern, reason in DEFAULT_IGNORED_GLOBS.items():
        if fnmatch.fnmatch(path.name, pattern):
            return reason
    return None


def list_non_git_files(root: Path) -> tuple[list[str], list[dict[str, str]]]:
    patterns = read_gitignore_patterns(root)
    included: list[str] = []
    excluded: list[dict[str, str]] = []

    for current, directory_names, file_names in os.walk(root, followlinks=False):
        current_path = Path(current)
        kept_directories: list[str] = []
        for name in sorted(directory_names):
            absolute = current_path / name
            relative = absolute.relative_to(root)
            rel = posix(relative)
            reason = default_exclusion(relative)
            if reason:
                excluded.append({"path": rel + "/", "reason": reason, "source": "safe-default"})
            elif ignored_by_patterns(rel, True, patterns):
                excluded.append({"path": rel + "/", "reason": "matched .gitignore", "source": ".gitignore"})
            elif absolute.is_symlink():
                included.append(rel)
            else:
                kept_directories.append(name)
        directory_names[:] = kept_directories

        for name in sorted(file_names):
            absolute = current_path / name
            relative = absolute.relative_to(root)
            rel = posix(relative)
            reason = default_exclusion(relative)
            if reason:
                excluded.append({"path": rel, "reason": reason, "source": "safe-default"})
            elif ignored_by_patterns(rel, False, patterns):
                excluded.append({"path": rel, "reason": "matched .gitignore", "source": ".gitignore"})
            else:
                included.append(rel)

    return sorted(set(included)), sorted(excluded, key=lambda item: item["path"])


def list_git_files(root: Path) -> tuple[list[str], set[str], list[dict[str, str]]]:
    tracked = set(null_split(run_git(["ls-files", "-z"], cwd=root).stdout))
    untracked = set(null_split(run_git(["ls-files", "-o", "--exclude-standard", "-z"], cwd=root).stdout))
    ignored = null_split(
        run_git(["ls-files", "-o", "-i", "--exclude-standard", "--directory", "-z"], cwd=root).stdout
    )
    excluded = [
        {"path": path, "reason": "ignored by Git", "source": "git-check-ignore"}
        for path in sorted(ignored)
    ]
    candidates = sorted(tracked | untracked)
    return candidates, tracked, excluded


def is_env_secret_name(name: str) -> bool:
    lowered = name.lower()
    if lowered == ".env" or lowered.startswith(".env."):
        return not lowered.endswith(SAFE_ENV_SUFFIXES)
    return False


def secret_filename_reason(relative: str) -> str | None:
    path = PurePosixPath(relative)
    lowered_name = path.name.lower()
    if is_env_secret_name(lowered_name):
        return "environment file may contain credentials"
    if lowered_name in SECRET_FILE_NAMES:
        return "credential or private-key filename"
    if path.suffix.lower() in SECRET_FILE_SUFFIXES:
        return "private key or keystore file type"
    return None


def probably_text(path: Path) -> bool:
    try:
        sample = path.read_bytes()[:8192]
    except OSError:
        return False
    return b"\x00" not in sample


def line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def is_placeholder(value: str) -> bool:
    lowered = value.lower()
    return any(marker in lowered for marker in PLACEHOLDER_MARKERS)


def scan_text_for_secrets(relative: str, absolute: Path) -> list[dict[str, Any]]:
    if absolute.stat().st_size > CONTENT_SCAN_LIMIT or not probably_text(absolute):
        return []
    text = absolute.read_text(encoding="utf-8", errors="replace")
    findings: list[dict[str, Any]] = []
    observed: set[tuple[str, int]] = set()

    for code, pattern in SECRET_PATTERNS:
        for match in pattern.finditer(text):
            line = line_number(text, match.start())
            key = (code, line)
            if key in observed:
                continue
            observed.add(key)
            findings.append(
                finding(
                    "blocker",
                    code,
                    relative,
                    f"Likely {code.replace('-', ' ')} detected; matched value is redacted",
                    line=line,
                )
            )

    for match in ASSIGNMENT_PATTERN.finditer(text):
        value = match.group("value")
        if is_placeholder(value):
            continue
        line = line_number(text, match.start())
        key = ("credential-assignment", line)
        if key in observed:
            continue
        observed.add(key)
        findings.append(
            finding(
                "blocker",
                "credential-assignment",
                relative,
                "A credential-like assignment contains a non-placeholder value; matched value is redacted",
                line=line,
            )
        )
    return findings


def package_metadata(root: Path) -> tuple[dict[str, str], list[dict[str, str]], list[str]]:
    scripts: dict[str, str] = {}
    entrypoints: list[dict[str, str]] = []
    types: list[str] = []

    package_file = root / "package.json"
    if package_file.is_file():
        types.append("Node.js")
        try:
            package = json.loads(package_file.read_text(encoding="utf-8"))
            raw_scripts = package.get("scripts", {})
            if isinstance(raw_scripts, dict):
                scripts = {str(key): str(value) for key, value in raw_scripts.items()}
            for key in ("main", "module", "browser"):
                value = package.get(key)
                if isinstance(value, str):
                    entrypoints.append({"path": value, "source": f"package.json:{key}"})
        except (OSError, json.JSONDecodeError, TypeError) as exc:
            entrypoints.append({"path": "package.json", "source": f"invalid JSON: {type(exc).__name__}"})

    if (root / "pyproject.toml").is_file() or (root / "requirements.txt").is_file():
        types.append("Python")
    if (root / "Cargo.toml").is_file():
        types.append("Rust")
    if (root / "go.mod").is_file():
        types.append("Go")

    skill_files = sorted(root.glob("*/SKILL.md"))
    if skill_files:
        types.append("Codex Skill collection")
        entrypoints.extend(
            {"path": posix(path.relative_to(root)), "source": "Codex Skill entry"}
            for path in skill_files
        )

    for name, label in (
        ("index.html", "conventional web entry"),
        ("main.py", "conventional Python entry"),
        ("app.py", "conventional Python entry"),
        ("manage.py", "Django entry"),
    ):
        if (root / name).is_file():
            entrypoints.append({"path": name, "source": label})

    html_count = len(list(root.glob("*.html")))
    if html_count:
        types.append("static web")
        if html_count == 1 and not any(item["path"].endswith(".html") for item in entrypoints):
            only_html = next(root.glob("*.html"))
            entrypoints.append({"path": only_html.name, "source": "only root HTML file"})

    return scripts, entrypoints, sorted(set(types)) or ["general source repository"]


def readiness(root: Path, scripts: dict[str, str], entrypoints: list[dict[str, str]]) -> dict[str, Any]:
    names = [path.name.lower() for path in root.iterdir() if path.is_file()]
    readmes = sorted(name for name in names if name.startswith("readme"))
    licenses = sorted(name for name in names if name.startswith(("license", "licence", "copying")))
    run_script_names = sorted(set(scripts) & {"start", "dev", "serve", "preview"})
    test_script_names = sorted(name for name in scripts if name == "test" or name.startswith("test:"))
    has_test_path = any((root / name).exists() for name in ("tests", "test", "spec", "__tests__"))
    return {
        "readme": {"present": bool(readmes), "files": readmes},
        "license": {"present": bool(licenses), "files": licenses},
        "gitignore": {"present": (root / ".gitignore").is_file()},
        "entrypoint": {"present": bool(entrypoints), "items": entrypoints},
        "runInstructions": {"detectedPackageScripts": run_script_names},
        "testInstructions": {"detectedPackageScripts": test_script_names, "testPathPresent": has_test_path},
    }


def observed_ignore_suggestions(root: Path) -> list[dict[str, str]]:
    suggestions: dict[str, str] = {}
    for current, directory_names, file_names in os.walk(root, followlinks=False):
        current_path = Path(current)
        for name in directory_names:
            if name in DEFAULT_IGNORED_DIRECTORIES and name != ".git":
                suggestions[f"{name}/"] = DEFAULT_IGNORED_DIRECTORIES[name]
        for name in file_names:
            if is_env_secret_name(name):
                suggestions[".env"] = "local environment credentials"
                suggestions[".env.*"] = "environment-specific credential files"
                suggestions["!.env.example"] = "keep a safe environment template"
                suggestions["!.env.sample"] = "keep a safe environment template"
            if name in DEFAULT_IGNORED_FILES:
                suggestions[name] = DEFAULT_IGNORED_FILES[name]
            for pattern, reason in DEFAULT_IGNORED_GLOBS.items():
                if fnmatch.fnmatch(name, pattern):
                    suggestions[pattern] = reason
        directory_names[:] = [name for name in directory_names if name not in {".git", "node_modules", ".venv", "venv"}]
    env_order = {".env": 0, ".env.*": 1, "!.env.example": 2, "!.env.sample": 3}
    ordered = sorted(
        suggestions.items(),
        key=lambda item: (0, env_order[item[0]]) if item[0] in env_order else (1, item[0]),
    )
    return [{"pattern": key, "reason": value} for key, value in ordered]


def build_manifest(project: Path | str) -> dict[str, Any]:
    root = Path(project).expanduser().resolve()
    if not root.is_dir():
        raise PublishError(f"Project directory does not exist: {root}")

    git = git_metadata(root)
    if git["isRepository"]:
        paths, tracked, excluded = list_git_files(root)
    else:
        paths, excluded = list_non_git_files(root)
        tracked = set()

    findings: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    extensions: Counter[str] = Counter()
    total_bytes = 0

    for relative in paths:
        absolute = root / Path(relative)
        if not absolute.exists() and not absolute.is_symlink():
            continue
        if absolute.is_dir() and not absolute.is_symlink():
            continue
        try:
            stat = absolute.lstat()
        except OSError as exc:
            findings.append(finding("warning", "unreadable-path", relative, f"Unable to inspect path: {exc}"))
            continue
        size = stat.st_size
        total_bytes += size
        suffix = Path(relative).suffix.lower() or "[no extension]"
        extensions[suffix] += 1
        candidates.append(
            {
                "path": relative,
                "bytes": size,
                "tracked": relative in tracked,
                "symlink": absolute.is_symlink(),
            }
        )

        filename_reason = secret_filename_reason(relative)
        if filename_reason:
            findings.append(
                finding(
                    "blocker",
                    "sensitive-filename",
                    relative,
                    f"Potentially sensitive file: {filename_reason}",
                )
            )
        if size > GITHUB_MAX_FILE_BYTES:
            findings.append(
                finding(
                    "blocker",
                    "github-file-limit",
                    relative,
                    "File exceeds GitHub's 100 MiB normal Git limit",
                    bytes=size,
                )
            )
        elif size >= LARGE_FILE_WARNING_BYTES:
            findings.append(
                finding(
                    "warning",
                    "large-file-review",
                    relative,
                    "File is at least 50 MiB; confirm whether Git LFS or a release artifact is more appropriate",
                    bytes=size,
                )
            )
        if absolute.is_symlink():
            findings.append(
                finding(
                    "warning",
                    "symlink-review",
                    relative,
                    "Review the symlink target and cross-platform behavior before publishing",
                )
            )
        elif size <= CONTENT_SCAN_LIMIT:
            try:
                findings.extend(scan_text_for_secrets(relative, absolute))
            except OSError as exc:
                findings.append(finding("warning", "content-scan-failed", relative, f"Unable to scan content: {exc}"))

    scripts, entrypoints, project_types = package_metadata(root)
    ready = readiness(root, scripts, entrypoints)
    if not ready["readme"]["present"]:
        findings.append(finding("warning", "missing-readme", None, "No root README file was detected"))
    if not ready["license"]["present"]:
        findings.append(
            finding(
                "warning",
                "missing-license",
                None,
                "No root license file was detected; do not infer a license without maintainer intent",
            )
        )
    if not ready["gitignore"]["present"]:
        findings.append(finding("warning", "missing-gitignore", None, "No root .gitignore file was detected"))
    if not ready["entrypoint"]["present"]:
        findings.append(finding("warning", "missing-entrypoint", None, "No conventional entry point was detected"))

    severity_counts = Counter(item["severity"] for item in findings)
    candidates.sort(key=lambda item: item["path"])
    findings.sort(key=lambda item: ({"blocker": 0, "warning": 1, "info": 2}.get(item["severity"], 3), item.get("path") or "", item["code"]))

    return {
        "schemaVersion": 1,
        "generatedAt": utc_now(),
        "project": {
            "name": root.name,
            "root": str(root),
            "types": project_types,
            "packageScripts": scripts,
            "entrypoints": entrypoints,
        },
        "git": git,
        "readiness": ready,
        "summary": {
            "candidateFiles": len(candidates),
            "candidateBytes": total_bytes,
            "ignoredPathEntries": len(excluded),
            "blockers": severity_counts["blocker"],
            "warnings": severity_counts["warning"],
            "topExtensions": [
                {"extension": extension, "files": count}
                for extension, count in extensions.most_common(20)
            ],
        },
        "candidateFiles": candidates,
        "excludedPaths": excluded,
        "findings": findings,
        "suggestedGitignore": observed_ignore_suggestions(root),
        "limitations": [
            "Secret detection is heuristic and does not replace GitHub Secret Scanning or credential rotation.",
            "Ignored Git directories may be summarized as directory entries rather than expanded file-by-file.",
            "Files larger than 2 MiB are checked for size and filename risk but not content-scanned.",
        ],
    }


def format_bytes(value: int) -> str:
    if value >= 1024 * 1024:
        return f"{value / 1024 / 1024:.1f} MiB"
    if value >= 1024:
        return f"{value / 1024:.1f} KiB"
    return f"{value} B"


def render_report(manifest: dict[str, Any]) -> str:
    summary = manifest["summary"]
    project = manifest["project"]
    lines = [
        f"# GitHub publication audit: {project['name']}",
        "",
        f"Generated: `{manifest['generatedAt']}`",
        "",
        "## Summary",
        "",
        "| Check | Result |",
        "| --- | ---: |",
        f"| Candidate files | {summary['candidateFiles']} |",
        f"| Candidate bytes | {format_bytes(summary['candidateBytes'])} |",
        f"| Ignored path entries | {summary['ignoredPathEntries']} |",
        f"| Blockers | {summary['blockers']} |",
        f"| Warnings | {summary['warnings']} |",
        "",
        "## Findings",
        "",
    ]
    if manifest["findings"]:
        for item in manifest["findings"]:
            location = f" `{item['path']}`" if item.get("path") else ""
            line = f":{item['line']}" if item.get("line") else ""
            lines.append(f"- **{item['severity'].upper()} / {item['code']}**{location}{line} — {item['message']}")
    else:
        lines.append("- No findings.")

    lines.extend(["", "## Candidate upload files", ""])
    if manifest["candidateFiles"]:
        for item in manifest["candidateFiles"]:
            state = "tracked" if item["tracked"] else "untracked"
            lines.append(f"- `{item['path']}` — {format_bytes(item['bytes'])}, {state}")
    else:
        lines.append("- None.")

    lines.extend(["", "## Excluded or ignored paths", ""])
    if manifest["excludedPaths"]:
        for item in manifest["excludedPaths"]:
            lines.append(f"- `{item['path']}` — {item['reason']} ({item['source']})")
    else:
        lines.append("- None detected.")

    lines.extend(["", "## Suggested `.gitignore` entries", ""])
    if manifest["suggestedGitignore"]:
        for item in manifest["suggestedGitignore"]:
            lines.append(f"- `{item['pattern']}` — {item['reason']}")
    else:
        lines.append("- No additional conservative entries were observed.")
    lines.append("")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect a local project before publishing it to GitHub")
    parser.add_argument("project", type=Path, help="Project root; for Git repositories this must be the worktree root")
    parser.add_argument("--json-out", type=Path, help="Write the complete machine-readable manifest")
    parser.add_argument("--report-out", type=Path, help="Write a Markdown review report")
    parser.add_argument("--fail-on-blockers", action="store_true", help="Exit with code 2 when blockers are found")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        manifest = build_manifest(args.project)
    except PublishError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 2

    write_json(args.json_out, manifest)
    if args.report_out:
        report_path = args.report_out.expanduser().resolve()
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(render_report(manifest), encoding="utf-8")

    summary = {
        "ok": manifest["summary"]["blockers"] == 0,
        "project": manifest["project"]["name"],
        **manifest["summary"],
        "jsonOut": str(args.json_out.resolve()) if args.json_out else None,
        "reportOut": str(args.report_out.resolve()) if args.report_out else None,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if args.fail_on_blockers and manifest["summary"]["blockers"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
