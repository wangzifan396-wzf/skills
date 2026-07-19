from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from validate_csdn_bundle import image_dimensions, render_report, text_outside_fences, validate_bundle, write_json


IMAGE_PATTERN = re.compile(r"!\[(?P<alt>[^\]]*)\]\((?P<target>[^)]+)\)")
CAPTION_PATTERN = re.compile(r"^\s*(?:>\s*)?[*_]?(?:图\s*\d+\s*[:：]|图注\s*[:：])(?P<caption>.+?)[*_]?\s*$")
GENERATED_FILES = {
    "article-source.md",
    "article-csdn.md",
    "publish-metadata.json",
    "image-map.json",
    "human-upload-checklist.md",
    "validation-report.json",
    "validation-report.md",
}


class BundleError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise BundleError(f"Metadata file does not exist: {path}") from exc
    except json.JSONDecodeError as exc:
        raise BundleError(f"Metadata JSON is invalid at line {exc.lineno}, column {exc.colno}") from exc
    if not isinstance(value, dict):
        raise BundleError("Metadata root must be a JSON object")
    return value


def safe_filename(value: str, fallback: str) -> str:
    stem = Path(value).stem.lower()
    cleaned = re.sub(r"[^a-z0-9]+", "-", stem).strip("-")
    return cleaned[:70] or fallback


def parse_image_target(raw: str) -> str:
    value = raw.strip()
    if value.startswith("<") and ">" in value:
        value = value[1 : value.index(">")]
    else:
        title_match = re.match(r"^(.*?)(?:\s+[\"'].*[\"'])?\s*$", value)
        value = title_match.group(1).strip() if title_match else value
    return unquote(value)


def is_remote(value: str) -> bool:
    return bool(re.match(r"^(?:https?:)?//|^data:", value, re.IGNORECASE))


def resolve_local_image(article: Path, target: str) -> Path:
    path = Path(target)
    if path.is_absolute():
        return path.resolve()
    return (article.parent / path).resolve()


def resolve_cover(metadata: Path, project_root: Path | None, cover: str) -> Path:
    value = Path(cover)
    if value.is_absolute():
        return value.resolve()
    base = project_root if project_root is not None else metadata.parent
    return (base / value).resolve()


def title_from_article(text: str) -> str:
    titles = re.findall(r"(?m)^#\s+(.+?)\s*$", text_outside_fences(text))
    if len(titles) != 1:
        raise BundleError(f"Authoring article must contain exactly one H1 title; found {len(titles)}")
    return titles[0].strip()


def remove_top_release_note(lines: list[str]) -> list[str]:
    index = 0
    while index < len(lines) and not lines[index].strip():
        index += 1
    if index >= len(lines) or not re.match(r"^#\s+", lines[index]):
        return lines
    index += 1
    while index < len(lines) and not lines[index].strip():
        index += 1
    if index >= len(lines) or not lines[index].lstrip().startswith(">"):
        return lines
    block_start = index
    block: list[str] = []
    while index < len(lines) and (lines[index].lstrip().startswith(">") or not lines[index].strip()):
        block.append(lines[index])
        index += 1
    block_text = "\n".join(block)
    if "发布说明（发布时可删除）" not in block_text:
        return lines
    remaining = lines[:block_start] + lines[index:]
    while block_start < len(remaining) and not remaining[block_start].strip():
        del remaining[block_start]
    return remaining


def remove_final_publication_section(lines: list[str]) -> list[str]:
    starts = [
        index
        for index, line in enumerate(lines)
        if re.match(r"^##\s+发布信息（发布时可删除）\s*$", line.strip())
    ]
    if not starts:
        return lines
    start = starts[-1]
    if any(re.match(r"^##\s+", line) for line in lines[start + 1 :]):
        return lines
    end = start
    while end > 0 and not lines[end - 1].strip():
        end -= 1
    if end > 0 and lines[end - 1].strip() == "---":
        end -= 1
        while end > 0 and not lines[end - 1].strip():
            end -= 1
    return lines[:end]


def cleanup_publication_notes(text: str) -> str:
    lines = text.splitlines()
    lines = remove_top_release_note(lines)
    lines = remove_final_publication_section(lines)
    result = "\n".join(lines).strip() + "\n"
    return result


def immediate_caption(text: str, match_end: int) -> str:
    remainder = text[match_end:]
    lines = remainder.splitlines()
    for line in lines:
        if not line.strip():
            continue
        match = CAPTION_PATTERN.match(line)
        return match.group("caption").strip() if match else ""
    return ""


def replace_images_outside_fences(text: str, callback) -> str:
    output: list[str] = []
    active: str | None = None
    offset = 0
    for line in text.splitlines(keepends=True):
        fence_match = re.match(r"\s*(`{3,}|~{3,})", line)
        if fence_match:
            token = fence_match.group(1)[0]
            if active is None:
                active = token
            elif active == token:
                active = None
            output.append(line)
        elif active is None:
            line_offset = offset
            output.append(IMAGE_PATTERN.sub(lambda match: callback(match, line_offset + match.end()), line))
        else:
            output.append(line)
        offset += len(line)
    return "".join(output)


def unique_name(images_directory: Path, desired: str, used: set[str]) -> str:
    stem = Path(desired).stem
    suffix = Path(desired).suffix
    candidate = desired
    counter = 2
    while candidate.lower() in used or (images_directory / candidate).exists():
        candidate = f"{stem}-{counter}{suffix}"
        counter += 1
    used.add(candidate.lower())
    return candidate


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ensure_output(output: Path, force: bool) -> Path:
    output.mkdir(parents=True, exist_ok=True)
    images = output / "images"
    images.mkdir(exist_ok=True)
    conflicts = [output / name for name in GENERATED_FILES if (output / name).exists()]
    conflicts.extend(images.glob("cover.*"))
    conflicts.extend(images.glob("[0-9][0-9]-*"))
    if conflicts and not force:
        names = ", ".join(str(path.relative_to(output)) for path in conflicts[:8])
        raise BundleError(f"Output contains generated files ({names}); rerun with --force to replace them")
    if force:
        for path in conflicts:
            if path.is_file():
                path.unlink()
    return images


def validate_metadata_input(metadata: dict[str, Any]) -> None:
    required = ("articleType", "category", "summary", "tags", "cover")
    missing = [field for field in required if not metadata.get(field)]
    if missing:
        raise BundleError(f"Metadata fields are required: {', '.join(missing)}")
    if not isinstance(metadata["tags"], list):
        raise BundleError("metadata.tags must be an array")
    if "alternativeTitles" in metadata and not isinstance(metadata["alternativeTitles"], list):
        raise BundleError("metadata.alternativeTitles must be an array")


def copy_image(source: Path, destination: Path) -> dict[str, Any]:
    if not source.is_file():
        raise BundleError(f"Image does not exist: {source}")
    dimensions = image_dimensions(source)
    if dimensions is None:
        raise BundleError(f"Unsupported or unreadable image format: {source}")
    shutil.copy2(source, destination)
    width, height = dimensions
    return {
        "bytes": destination.stat().st_size,
        "sha256": sha256(destination),
        "dimensions": {"width": width, "height": height},
    }


def build_bundle(article_value: Path, metadata_value: Path, output_value: Path, project_root_value: Path | None, force: bool) -> dict[str, Any]:
    article = article_value.expanduser().resolve()
    metadata_path = metadata_value.expanduser().resolve()
    output = output_value.expanduser().resolve()
    project_root = project_root_value.expanduser().resolve() if project_root_value else None
    if not article.is_file():
        raise BundleError(f"Authoring article does not exist: {article}")
    if project_root is not None and not project_root.is_dir():
        raise BundleError(f"Project root does not exist: {project_root}")

    source_text = article.read_text(encoding="utf-8")
    metadata = load_json(metadata_path)
    validate_metadata_input(metadata)
    title = title_from_article(source_text)
    if metadata.get("title") and metadata["title"] != title:
        raise BundleError("metadata.title must match the article H1")

    images_directory = ensure_output(output, force)
    used_names: set[str] = set()

    cover_source = resolve_cover(metadata_path, project_root, str(metadata["cover"]))
    cover_suffix = cover_source.suffix.lower() or ".jpg"
    cover_name = unique_name(images_directory, f"cover{cover_suffix}", used_names)
    cover_destination = images_directory / cover_name
    cover_details = copy_image(cover_source, cover_destination)
    cover_map = {
        "sourceReference": str(metadata["cover"]),
        "packaged": f"images/{cover_name}",
        **cover_details,
    }

    body_images: list[dict[str, Any]] = []
    remote_images: list[dict[str, str]] = []

    def replace_image(match: re.Match[str], match_end: int) -> str:
        target = parse_image_target(match.group("target"))
        alt = match.group("alt").strip()
        if is_remote(target):
            remote_images.append({"target": target, "alt": alt})
            return match.group(0)
        number = len(body_images) + 1
        source = resolve_local_image(article, target)
        suffix = source.suffix.lower() or ".jpg"
        desired = f"{number:02d}-{safe_filename(source.name, f'image-{number:02d}')}{suffix}"
        packaged_name = unique_name(images_directory, desired, used_names)
        destination = images_directory / packaged_name
        details = copy_image(source, destination)
        packaged = f"images/{packaged_name}"
        marker = f"【配图 {number:02d}：请上传 {packaged} 后删除本行】"
        entry = {
            "number": number,
            "marker": marker,
            "sourceReference": target,
            "packaged": packaged,
            "alt": alt,
            "caption": immediate_caption(clean_text, match_end),
            **details,
        }
        body_images.append(entry)
        return f"> {marker}"

    clean_text = cleanup_publication_notes(source_text)
    paste_ready = replace_images_outside_fences(clean_text, replace_image)

    source_destination = output / "article-source.md"
    article_destination = output / "article-csdn.md"
    source_destination.write_text(source_text.rstrip() + "\n", encoding="utf-8")
    article_destination.write_text(paste_ready.rstrip() + "\n", encoding="utf-8")

    alternative_titles = metadata.get("alternativeTitles", [])
    packaged_metadata = {
        "schemaVersion": 1,
        "generatedAt": utc_now(),
        "title": title,
        "articleType": metadata["articleType"],
        "category": metadata["category"],
        "backupCategories": metadata.get("backupCategories", []),
        "summary": metadata["summary"],
        "tags": metadata["tags"],
        "alternativeTitles": alternative_titles,
        "coverPackaged": cover_map["packaged"],
        "repositoryUrl": metadata.get("repositoryUrl", ""),
        "sourceCommit": metadata.get("sourceCommit", ""),
        "notes": metadata.get("notes", []),
        "bodyImageCount": len(body_images),
        "remoteImageCount": len(remote_images),
    }
    image_map = {
        "schemaVersion": 1,
        "generatedAt": utc_now(),
        "cover": cover_map,
        "bodyImages": body_images,
        "remoteImages": remote_images,
    }
    write_json(output / "publish-metadata.json", packaged_metadata)
    write_json(output / "image-map.json", image_map)

    checklist = [
        "# CSDN 人工发布检查表",
        "",
        "## 粘贴与配图",
        "",
        "1. 打开 CSDN Markdown 编辑器并新建文章。",
        "2. 将 `article-csdn.md` 全文粘贴到正文。",
    ]
    step = 3
    for item in body_images:
        checklist.append(
            f"{step}. 搜索完整标记 `{item['marker']}`，在该处上传 `{item['packaged']}`，确认预览后删除整行标记。"
        )
        if item["caption"]:
            checklist.append(f"   - 保留紧随其后的图注：{item['caption']}")
        step += 1
    checklist.extend(
        [
            f"{step}. 将 `{cover_map['packaged']}` 设置为文章封面；正文中无需重复插入。",
            "",
            "## 发布信息",
            "",
            f"- 标题：{title}",
            f"- 文章类型：{metadata['articleType']}",
            f"- 推荐分区：{metadata['category']}",
            f"- 摘要：{metadata['summary']}",
            f"- 标签：{'、'.join(str(tag) for tag in metadata['tags'])}",
        ]
    )
    if metadata.get("backupCategories"):
        checklist.append(f"- 备选分区：{'、'.join(str(value) for value in metadata['backupCategories'])}")
    if alternative_titles:
        checklist.append("- 备选标题：")
        checklist.extend(f"  - {value}" for value in alternative_titles)
    if metadata.get("notes"):
        checklist.append("- 发布备注：")
        checklist.extend(f"  - {value}" for value in metadata["notes"])
    checklist.extend(
        [
            "",
            "## 最终核对",
            "",
            "- [ ] 正文中已没有 `【配图】` 标记。",
            "- [ ] 封面和每张正文图均清晰、顺序正确、没有隐私信息。",
            "- [ ] 代码块、表格、链接和目录在预览中正常。",
            "- [ ] 标题、摘要、分类、标签和原创类型已经填写。",
            "- [ ] 已删除所有只给发布者看的备注。",
            "- [ ] 已选择“保存草稿”或由作者本人确认公开发布。",
            "",
        ]
    )
    (output / "human-upload-checklist.md").write_text("\n".join(checklist), encoding="utf-8")

    report = validate_bundle(output)
    write_json(output / "validation-report.json", report)
    (output / "validation-report.md").write_text(render_report(report), encoding="utf-8")
    return {
        "schemaVersion": 1,
        "output": str(output),
        "valid": report["valid"],
        "title": title,
        "bodyImages": len(body_images),
        "remoteImages": len(remote_images),
        "blockers": report["summary"]["blockers"],
        "warnings": report["summary"]["warnings"],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Package an authoring Markdown file as a human-publishable CSDN bundle")
    parser.add_argument("--article", required=True, type=Path, help="Authoring Markdown source")
    parser.add_argument("--metadata", required=True, type=Path, help="Publication metadata JSON")
    parser.add_argument("--project-root", type=Path, help="Base directory for metadata cover paths")
    parser.add_argument("--output", required=True, type=Path, help="Bundle directory")
    parser.add_argument("--force", action="store_true", help="Replace only known generated bundle files")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = build_bundle(args.article, args.metadata, args.output, args.project_root, args.force)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["valid"] else 2
    except (BundleError, OSError) as exc:
        print(json.dumps({"valid": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
