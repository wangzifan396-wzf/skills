from __future__ import annotations

import binascii
import json
import re
import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "prepare-csdn-draft" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import package_csdn_draft  # noqa: E402
import validate_csdn_bundle  # noqa: E402


def png_chunk(name: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + name + data + struct.pack(">I", binascii.crc32(name + data) & 0xFFFFFFFF)


def write_png(path: Path, width: int, height: int, color: tuple[int, int, int] = (20, 80, 120)) -> None:
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    row = b"\x00" + bytes(color) * width
    pixels = zlib.compress(row * height, level=9)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + png_chunk(b"IHDR", header) + png_chunk(b"IDAT", pixels) + png_chunk(b"IEND", b""))


def article_text() -> str:
    paragraph = (
        "这个段落使用真实项目证据解释一个可复用的工程方法。它说明问题、设计取舍、验证步骤和限制，"
        "并避免把配置目标写成测量结果。为了让测试稿达到完整技术文章的长度，这段内容会重复出现。"
    )
    body = "\n\n".join(paragraph for _ in range(12))
    return f"""# 用真实项目准备一篇完整的 CSDN 技术草稿

> 发布说明（发布时可删除）
>
> - 文章类型：原创。
> - 封面：`cover.png`。
> - 正文图 1：`diagram.png`，放在流程一节。

开场先说明读者遇到的问题，以及本文可以复用的结果。

## 为什么需要这套流程

{body}

```markdown
# 代码示例里的标题

![代码示例里的图片语法](missing-in-code.png)
```

## 真实流程

![流程图](images/diagram.png)

> 图 1：流程图展示输入、检查与发布包之间的关系。

{body}

## 限制与复现

{body}

---

## 发布信息（发布时可删除）

- 推荐标签：测试、CSDN、自动化。
"""


def metadata() -> dict:
    return {
        "articleType": "原创",
        "category": "人工智能 / 开发工具",
        "backupCategories": ["软件工程"],
        "summary": "本文从真实项目证据出发，展示如何生成技术正文、整理封面与正文图片位置、填写摘要分区和标签，并用确定性脚本验证最终 CSDN 草稿发布包，减少人工发布前的重复检查。",
        "tags": ["CSDN", "AI 编程", "自动化"],
        "alternativeTitles": ["把技术文章整理成可直接发布的 CSDN 草稿包"],
        "cover": "cover.png",
        "repositoryUrl": "https://github.com/example/project",
        "sourceCommit": "0123456789abcdef0123456789abcdef01234567",
        "notes": ["发布前检查图片预览。"],
    }


class CsdnBundleTests(unittest.TestCase):
    def make_fixture(self, root: Path) -> tuple[Path, Path]:
        docs = root / "docs"
        images = docs / "images"
        images.mkdir(parents=True)
        write_png(root / "cover.png", 1920, 1080)
        write_png(images / "diagram.png", 1600, 900)
        article = docs / "article.md"
        article.write_text(article_text(), encoding="utf-8")
        config = root / "metadata.json"
        config.write_text(json.dumps(metadata(), ensure_ascii=False, indent=2), encoding="utf-8")
        return article, config

    def test_realistic_bundle_is_complete_and_valid(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            article, config = self.make_fixture(root)
            output = root / "bundle"

            result = package_csdn_draft.build_bundle(article, config, output, root, False)
            self.assertTrue(result["valid"])
            self.assertEqual(result["bodyImages"], 1)
            self.assertEqual(result["warnings"], 0)

            paste_ready = (output / "article-csdn.md").read_text(encoding="utf-8")
            self.assertNotIn("发布说明（发布时可删除）", paste_ready)
            self.assertNotIn("发布信息（发布时可删除）", paste_ready)
            self.assertIn("【配图 01：请上传 images/01-diagram.png 后删除本行】", paste_ready)
            self.assertIn("missing-in-code.png", paste_ready)

            mapping = json.loads((output / "image-map.json").read_text(encoding="utf-8"))
            self.assertEqual(mapping["bodyImages"][0]["sourceReference"], "images/diagram.png")
            self.assertNotIn(str(root), json.dumps(mapping, ensure_ascii=False))
            self.assertEqual(mapping["bodyImages"][0]["caption"], "流程图展示输入、检查与发布包之间的关系。")
            checklist = (output / "human-upload-checklist.md").read_text(encoding="utf-8")
            self.assertIn("搜索完整标记 `【配图 01：请上传 images/01-diagram.png 后删除本行】`", checklist)

            report = validate_csdn_bundle.validate_bundle(output)
            self.assertTrue(report["valid"])
            self.assertEqual(report["summary"]["blockers"], 0)
            self.assertEqual(report["summary"]["warnings"], 0)

    def test_force_replaces_generated_files_but_preserves_unrelated_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            article, config = self.make_fixture(root)
            output = root / "bundle"
            package_csdn_draft.build_bundle(article, config, output, root, False)
            unrelated = output / "keep-me.txt"
            unrelated.write_text("user file\n", encoding="utf-8")

            with self.assertRaises(package_csdn_draft.BundleError):
                package_csdn_draft.build_bundle(article, config, output, root, False)

            result = package_csdn_draft.build_bundle(article, config, output, root, True)
            self.assertTrue(result["valid"])
            self.assertEqual(unrelated.read_text(encoding="utf-8"), "user file\n")

    def test_missing_local_image_stops_packaging(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            article, config = self.make_fixture(root)
            (root / "docs" / "images" / "diagram.png").unlink()
            with self.assertRaises(package_csdn_draft.BundleError):
                package_csdn_draft.build_bundle(article, config, root / "bundle", root, False)

    def test_validator_detects_removed_marker(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            article, config = self.make_fixture(root)
            output = root / "bundle"
            package_csdn_draft.build_bundle(article, config, output, root, False)
            paste_ready = output / "article-csdn.md"
            text = paste_ready.read_text(encoding="utf-8")
            paste_ready.write_text(re.sub(r"(?m)^> 【配图 01.*\n", "", text), encoding="utf-8")

            report = validate_csdn_bundle.validate_bundle(output)
            self.assertFalse(report["valid"])
            self.assertTrue(any(item["code"] == "marker-map-count" for item in report["issues"]))

    def test_rule_names_in_prose_and_inline_code_are_not_false_blockers(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            article, config = self.make_fixture(root)
            output = root / "bundle"
            package_csdn_draft.build_bundle(article, config, output, root, False)
            paste_ready = output / "article-csdn.md"
            text = paste_ready.read_text(encoding="utf-8")
            text += "\n本文可以讨论发布说明（发布时可删除）的设计，并解释为什么校验器会检查 `TODO`。\n"
            paste_ready.write_text(text, encoding="utf-8")

            report = validate_csdn_bundle.validate_bundle(output)
            self.assertTrue(report["valid"])
            self.assertFalse(any(item["code"] in {"internal-publication-note", "unfinished-placeholder"} for item in report["issues"]))


if __name__ == "__main__":
    unittest.main()
