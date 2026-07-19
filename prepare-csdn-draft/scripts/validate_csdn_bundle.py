from __future__ import annotations

import argparse
import json
import re
import struct
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REQUIRED_FILES = (
    "article-source.md",
    "article-csdn.md",
    "publish-metadata.json",
    "image-map.json",
    "human-upload-checklist.md",
)
MARKER_PATTERN = re.compile(r"【配图\s*(\d{2})：请上传\s+([^\s]+)\s+后删除本行】")
MARKDOWN_IMAGE_PATTERN = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")
PUBLICATION_NOTE_PATTERN = re.compile(
    r"(?m)^\s*>\s*发布说明（发布时可删除）\s*$|^\s*##\s+发布信息（发布时可删除）\s*$"
)
UNFINISHED_PATTERN = re.compile(r"\b(?:TODO|TBD|PLACEHOLDER)\b|待补内容|此处插图", re.IGNORECASE)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def issue(severity: str, code: str, message: str, path: str | None = None, **extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "severity": severity,
        "code": code,
        "path": path,
        "message": message,
    }
    payload.update(extra)
    return payload


def read_json(path: Path, issues: list[dict[str, Any]]) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        issues.append(issue("blocker", "missing-file", "Required JSON file is missing", path.name))
    except json.JSONDecodeError as exc:
        issues.append(
            issue(
                "blocker",
                "invalid-json",
                f"Invalid JSON at line {exc.lineno}, column {exc.colno}",
                path.name,
            )
        )
    except OSError as exc:
        issues.append(issue("blocker", "unreadable-file", f"Unable to read file: {exc}", path.name))
    return {}


def text_outside_fences(text: str) -> str:
    output: list[str] = []
    active: str | None = None
    for line in text.splitlines():
        stripped = line.lstrip()
        fence_match = re.match(r"(`{3,}|~{3,})", stripped)
        if fence_match:
            token = fence_match.group(1)[0]
            if active is None:
                active = token
            elif active == token:
                active = None
            output.append("")
        elif active is None:
            output.append(line)
        else:
            output.append("")
    return "\n".join(output)


def fence_balance(text: str) -> tuple[bool, int]:
    active: str | None = None
    count = 0
    for line in text.splitlines():
        match = re.match(r"\s*(`{3,}|~{3,})", line)
        if not match:
            continue
        token = match.group(1)[0]
        if active is None:
            active = token
            count += 1
        elif active == token:
            active = None
            count += 1
    return active is None, count


def extract_h1(text: str) -> list[str]:
    return [match.group(1).strip() for match in re.finditer(r"(?m)^#\s+(.+?)\s*$", text_outside_fences(text))]


def jpeg_dimensions(data: bytes) -> tuple[int, int] | None:
    if len(data) < 4 or data[:2] != b"\xff\xd8":
        return None
    index = 2
    sof_markers = {
        0xC0,
        0xC1,
        0xC2,
        0xC3,
        0xC5,
        0xC6,
        0xC7,
        0xC9,
        0xCA,
        0xCB,
        0xCD,
        0xCE,
        0xCF,
    }
    while index + 3 < len(data):
        if data[index] != 0xFF:
            index += 1
            continue
        while index < len(data) and data[index] == 0xFF:
            index += 1
        if index >= len(data):
            break
        marker = data[index]
        index += 1
        if marker in {0xD8, 0xD9}:
            continue
        if marker == 0xDA:
            break
        if index + 2 > len(data):
            break
        length = struct.unpack(">H", data[index : index + 2])[0]
        if length < 2 or index + length > len(data):
            break
        if marker in sof_markers and length >= 7:
            height = struct.unpack(">H", data[index + 3 : index + 5])[0]
            width = struct.unpack(">H", data[index + 5 : index + 7])[0]
            return width, height
        index += length
    return None


def image_dimensions(path: Path) -> tuple[int, int] | None:
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if len(data) >= 24 and data[:8] == b"\x89PNG\r\n\x1a\n":
        return struct.unpack(">II", data[16:24])
    if len(data) >= 10 and data[:6] in {b"GIF87a", b"GIF89a"}:
        return struct.unpack("<HH", data[6:10])
    return jpeg_dimensions(data)


def path_from_bundle(bundle: Path, relative: str) -> Path | None:
    candidate = (bundle / relative).resolve()
    try:
        candidate.relative_to(bundle)
    except ValueError:
        return None
    return candidate


def validate_bundle(bundle_value: Path | str) -> dict[str, Any]:
    bundle = Path(bundle_value).expanduser().resolve()
    issues: list[dict[str, Any]] = []
    if not bundle.is_dir():
        return {
            "schemaVersion": 1,
            "validatedAt": utc_now(),
            "bundle": str(bundle),
            "valid": False,
            "summary": {"blockers": 1, "warnings": 0},
            "issues": [issue("blocker", "missing-bundle", "Bundle directory does not exist")],
        }

    for name in REQUIRED_FILES:
        if not (bundle / name).is_file():
            issues.append(issue("blocker", "missing-file", "Required bundle file is missing", name))
    if not (bundle / "images").is_dir():
        issues.append(issue("blocker", "missing-images-directory", "Required images directory is missing", "images/"))

    source_path = bundle / "article-source.md"
    article_path = bundle / "article-csdn.md"
    source_text = source_path.read_text(encoding="utf-8", errors="replace") if source_path.is_file() else ""
    article_text = article_path.read_text(encoding="utf-8", errors="replace") if article_path.is_file() else ""
    metadata = read_json(bundle / "publish-metadata.json", issues)
    image_map = read_json(bundle / "image-map.json", issues)

    h1 = extract_h1(article_text)
    source_h1 = extract_h1(source_text)
    if len(h1) != 1:
        issues.append(issue("blocker", "invalid-h1-count", f"Paste-ready article must contain one H1; found {len(h1)}", "article-csdn.md"))
    if len(source_h1) != 1:
        issues.append(issue("blocker", "invalid-source-h1-count", f"Source article must contain one H1; found {len(source_h1)}", "article-source.md"))
    if h1 and source_h1 and h1[0] != source_h1[0]:
        issues.append(issue("blocker", "title-mismatch", "Source and paste-ready H1 titles differ"))
    if h1 and metadata.get("title") != h1[0]:
        issues.append(issue("blocker", "metadata-title-mismatch", "Metadata title does not match article H1", "publish-metadata.json"))
    if h1 and not 10 <= len(h1[0]) <= 80:
        issues.append(issue("warning", "title-length", f"Title length is {len(h1[0])}; review mobile readability and specificity"))

    balanced, fence_count = fence_balance(article_text)
    if not balanced:
        issues.append(issue("blocker", "unmatched-code-fence", "Paste-ready article contains an unmatched fenced code block", "article-csdn.md"))
    outside = text_outside_fences(article_text)
    outside_no_inline_code = re.sub(r"`[^`\n]*`", "", outside)
    if PUBLICATION_NOTE_PATTERN.search(outside_no_inline_code):
        issues.append(issue("blocker", "internal-publication-note", "Paste-ready body still contains removable publication notes", "article-csdn.md"))
    unfinished = sorted(set(match.group(0) for match in UNFINISHED_PATTERN.finditer(outside_no_inline_code)))
    if unfinished:
        issues.append(issue("blocker", "unfinished-placeholder", f"Unfinished markers remain: {', '.join(unfinished)}", "article-csdn.md"))
    if re.search(r"file://|(?<![\w])(?:[A-Za-z]:[\\/]|/Users/|/home/)", outside_no_inline_code, re.IGNORECASE):
        issues.append(issue("blocker", "local-absolute-path", "Paste-ready prose contains a local absolute path", "article-csdn.md"))

    local_markdown_images = []
    remote_markdown_images = []
    for match in MARKDOWN_IMAGE_PATTERN.finditer(outside_no_inline_code):
        target = match.group(1).strip().strip("<>").split()[0]
        if re.match(r"https?://", target, re.IGNORECASE):
            remote_markdown_images.append(target)
        else:
            local_markdown_images.append(target)
    if local_markdown_images:
        issues.append(issue("blocker", "unpackaged-local-image", "Paste-ready article still contains local Markdown image paths", "article-csdn.md"))
    if remote_markdown_images:
        issues.append(issue("warning", "remote-image", f"Article retains {len(remote_markdown_images)} remote image(s); verify availability and rights", "article-csdn.md"))

    markers = [(int(number), path) for number, path in MARKER_PATTERN.findall(outside_no_inline_code)]
    marker_numbers = [number for number, _ in markers]
    expected_numbers = list(range(1, len(markers) + 1))
    if marker_numbers != expected_numbers:
        issues.append(issue("blocker", "marker-order", f"Image markers must be consecutive from 01; found {marker_numbers}", "article-csdn.md"))

    body_images = image_map.get("bodyImages", []) if isinstance(image_map, dict) else []
    if not isinstance(body_images, list):
        issues.append(issue("blocker", "invalid-image-map", "bodyImages must be an array", "image-map.json"))
        body_images = []
    if len(markers) != len(body_images):
        issues.append(issue("blocker", "marker-map-count", f"Found {len(markers)} markers but {len(body_images)} body image map entries"))

    for index, item in enumerate(body_images, start=1):
        if not isinstance(item, dict):
            issues.append(issue("blocker", "invalid-image-entry", f"Body image entry {index} is not an object", "image-map.json"))
            continue
        packaged = str(item.get("packaged", ""))
        expected_marker = f"{index:02d}"
        if item.get("number") != index:
            issues.append(issue("blocker", "image-number", f"Body image entry {index} has the wrong number", "image-map.json"))
        if index <= len(markers) and (markers[index - 1][0] != index or markers[index - 1][1] != packaged):
            issues.append(issue("blocker", "marker-map-mismatch", f"Marker {expected_marker} does not match image-map path {packaged}"))
        file_path = path_from_bundle(bundle, packaged) if packaged else None
        if file_path is None or not file_path.is_file():
            issues.append(issue("blocker", "missing-body-image", "Packaged body image is missing or escapes the bundle", packaged or None))
            continue
        actual_dimensions = image_dimensions(file_path)
        if actual_dimensions is None:
            issues.append(issue("warning", "unknown-image-dimensions", "Could not read image dimensions using the standard-library validator", packaged))
        else:
            width, height = actual_dimensions
            declared = item.get("dimensions") or {}
            if declared.get("width") != width or declared.get("height") != height:
                issues.append(issue("blocker", "image-dimension-mismatch", f"Declared dimensions do not match {width}×{height}", packaged))
            if width < 1000:
                issues.append(issue("warning", "small-body-image", f"Body image width is {width}px; verify text readability", packaged))
        if not str(item.get("alt", "")).strip():
            issues.append(issue("warning", "missing-image-alt", "Body image alt text is empty", packaged))
        if not str(item.get("caption", "")).strip():
            issues.append(issue("warning", "missing-image-caption", "No immediate image caption was detected", packaged))

    cover = image_map.get("cover") if isinstance(image_map, dict) else None
    if not isinstance(cover, dict):
        issues.append(issue("blocker", "missing-cover-map", "image-map.json must contain a cover object", "image-map.json"))
    else:
        cover_packaged = str(cover.get("packaged", ""))
        cover_path = path_from_bundle(bundle, cover_packaged) if cover_packaged else None
        if cover_path is None or not cover_path.is_file():
            issues.append(issue("blocker", "missing-cover", "Packaged cover is missing or escapes the bundle", cover_packaged or None))
        else:
            dimensions = image_dimensions(cover_path)
            if dimensions is None:
                issues.append(issue("warning", "unknown-cover-dimensions", "Could not read cover dimensions", cover_packaged))
            else:
                width, height = dimensions
                declared = cover.get("dimensions") or {}
                if declared.get("width") != width or declared.get("height") != height:
                    issues.append(issue("blocker", "cover-dimension-mismatch", f"Declared dimensions do not match {width}×{height}", cover_packaged))
                ratio = width / height if height else 0
                if width < 1200 or not 1.70 <= ratio <= 1.82:
                    issues.append(issue("warning", "cover-shape", f"Cover is {width}×{height}; prefer at least 1200px wide and approximately 16:9", cover_packaged))

    required_metadata = ("articleType", "category", "summary", "tags", "coverPackaged")
    for field in required_metadata:
        if not metadata.get(field):
            issues.append(issue("blocker", "missing-metadata", f"Required metadata field is empty: {field}", "publish-metadata.json"))
    summary_text = str(metadata.get("summary", "")).strip()
    if summary_text and not 60 <= len(summary_text) <= 320:
        issues.append(issue("warning", "summary-length", f"Summary length is {len(summary_text)}; review CSDN preview quality", "publish-metadata.json"))
    tags = metadata.get("tags", [])
    if not isinstance(tags, list):
        issues.append(issue("blocker", "invalid-tags", "tags must be an array", "publish-metadata.json"))
    elif not 3 <= len(tags) <= 5:
        issues.append(issue("warning", "tag-count", f"Found {len(tags)} tags; prefer 3-5 specific tags", "publish-metadata.json"))
    alternatives = metadata.get("alternativeTitles", [])
    if not isinstance(alternatives, list):
        issues.append(issue("blocker", "invalid-alternative-titles", "alternativeTitles must be an array", "publish-metadata.json"))
    elif len(alternatives) > 3:
        issues.append(issue("warning", "alternative-title-count", "More than three alternative titles were provided", "publish-metadata.json"))

    body_without_markers = MARKER_PATTERN.sub("", outside)
    character_count = len(re.sub(r"\s+", "", body_without_markers))
    h2_count = len(re.findall(r"(?m)^##\s+", outside))
    if character_count < 1200:
        issues.append(issue("warning", "short-article", f"Reader-facing article has about {character_count} non-whitespace characters"))
    if h2_count < 3:
        issues.append(issue("warning", "few-sections", f"Reader-facing article has {h2_count} H2 sections"))

    counts = Counter(item["severity"] for item in issues)
    issues.sort(key=lambda item: ({"blocker": 0, "warning": 1}.get(item["severity"], 2), item.get("path") or "", item["code"]))
    return {
        "schemaVersion": 1,
        "validatedAt": utc_now(),
        "bundle": str(bundle),
        "valid": counts["blocker"] == 0,
        "summary": {
            "blockers": counts["blocker"],
            "warnings": counts["warning"],
            "articleCharacters": character_count,
            "h2Sections": h2_count,
            "codeFences": fence_count,
            "bodyImages": len(body_images),
        },
        "issues": issues,
    }


def render_report(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# CSDN draft bundle validation",
        "",
        f"Validated: `{report['validatedAt']}`",
        "",
        "| Check | Result |",
        "| --- | ---: |",
        f"| Valid | {'yes' if report['valid'] else 'no'} |",
        f"| Blockers | {summary['blockers']} |",
        f"| Warnings | {summary['warnings']} |",
        f"| Article characters | {summary.get('articleCharacters', 0)} |",
        f"| H2 sections | {summary.get('h2Sections', 0)} |",
        f"| Body images | {summary.get('bodyImages', 0)} |",
        "",
        "## Findings",
        "",
    ]
    if not report["issues"]:
        lines.append("- No findings.")
    else:
        for item in report["issues"]:
            location = f" `{item['path']}`" if item.get("path") else ""
            lines.append(f"- **{item['severity'].upper()} / {item['code']}**{location} — {item['message']}")
    lines.append("")
    return "\n".join(lines)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate a packaged CSDN draft bundle")
    parser.add_argument("--bundle", required=True, type=Path, help="Bundle directory")
    parser.add_argument("--json-out", type=Path, help="JSON report path (default: bundle/validation-report.json)")
    parser.add_argument("--report-out", type=Path, help="Markdown report path (default: bundle/validation-report.md)")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    bundle = args.bundle.expanduser().resolve()
    report = validate_bundle(bundle)
    json_out = args.json_out.expanduser().resolve() if args.json_out else bundle / "validation-report.json"
    markdown_out = args.report_out.expanduser().resolve() if args.report_out else bundle / "validation-report.md"
    write_json(json_out, report)
    markdown_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.write_text(render_report(report), encoding="utf-8")
    print(json.dumps({"valid": report["valid"], **report["summary"], "jsonOut": str(json_out), "reportOut": str(markdown_out)}, ensure_ascii=False, indent=2))
    return 0 if report["valid"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
