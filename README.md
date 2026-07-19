# Codex Skills

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)

这里收录可安装、可审计、带确定性脚本的 Codex Skills。目前包括安全发布 GitHub 项目、
准备 CSDN 技术文章发布包，以及制作网页项目横竖版宣传视频三条工作流。

## Skills

| Skill | 用途 | 状态 |
| --- | --- | --- |
| [`github-safe-publish`](github-safe-publish/) | 审计本地项目，生成上传/排除清单，并在明确授权后安全提交、推送和校验 GitHub 仓库 | V1 |
| [`prepare-csdn-draft`](prepare-csdn-draft/) | 生成并验证 CSDN 技术文章、封面/正文图清单、准确配图标记、摘要、分区、标签和人工发布检查表 | V1 |
| [`build-web-promo-video`](build-web-promo-video/) | 录制真实网页场景，生成配音/BGM/字幕、横竖版视频、联系表和 FFprobe 质检报告 | V1 |

## 安装

只安装需要的 Skill，将 `<skill-name>` 替换为上表中的名称：

```powershell
git clone https://github.com/wangzifan396-wzf/skills.git
Copy-Item -Recurse ".\skills\<skill-name>" "$HOME\.codex\skills\<skill-name>"
```

macOS / Linux：

```bash
git clone https://github.com/wangzifan396-wzf/skills.git
cp -R "skills/<skill-name>" "$HOME/.codex/skills/<skill-name>"
```

重启 Codex 后，可以这样调用：

```text
使用 $github-safe-publish，检查当前项目，并发布到
https://github.com/OWNER/REPOSITORY 。
```

```text
使用 $prepare-csdn-draft，根据当前项目生成一篇完整的 CSDN 技术文章发布包，
标明封面、每张正文图的位置、摘要、分区和标签，不要操作 CSDN 网站。
```

```text
使用 $build-web-promo-video，为当前网页项目制作一套包含横版、竖版、无字幕版、
字幕版和质检报告的完整宣传视频。
```

`github-safe-publish` 必须获得明确目标和推送授权；另外两个 Skill 只生成本地文件，不会
登录、编辑、上传或发布到第三方平台。

## GitHub 安全发布会检查什么

- Git 工作树、当前分支、现有远端和待提交内容；
- `.env`、私钥、常见平台令牌和疑似凭据赋值；
- `node_modules`、虚拟环境、缓存、日志和临时文件；
- GitHub 100 MiB 单文件限制与需要复核的大文件；
- README、LICENSE、`.gitignore`、项目入口、运行和测试命令；
- 目标 GitHub 仓库是否为空、是否与本地历史兼容；
- 推送后的本地 `HEAD` 与远端分支 SHA 是否一致。

扫描器输出机器可读 JSON 和人工复核 Markdown。发布器默认只做 dry-run，必须增加
`--execute` 和与 URL 一致的 `--confirm-repository OWNER/REPO` 才会产生提交和推送。

## 直接运行脚本

```powershell
python github-safe-publish/scripts/inspect_project.py D:\path\to\project `
  --json-out audit.json --report-out audit.md

python github-safe-publish/scripts/inspect_remote.py `
  https://github.com/OWNER/REPOSITORY --json-out remote.json

python github-safe-publish/scripts/publish_project.py `
  --project D:\path\to\project `
  --remote https://github.com/OWNER/REPOSITORY `
  --confirm-repository OWNER/REPOSITORY `
  --commit-message "chore: publish project"
```

最后一条命令仍是 dry-run。确认审计结果后再原样增加 `--execute`。

## CSDN 草稿发布包

`prepare-csdn-draft` 将作者源稿和发布元数据整理为：

- 去除内部备注、带准确 `【配图 01】` 标记的 CSDN 粘贴稿；
- 编号后的封面与正文图片；
- 图片来源、位置、图注、尺寸和哈希映射；
- 推荐标题、摘要、原创类型、分区、备选分区、标签和备选标题；
- 逐项人工上传检查表与机器可读验证报告。

```powershell
python prepare-csdn-draft/scripts/package_csdn_draft.py `
  --article D:\path\to\article.md `
  --metadata D:\path\to\metadata.json `
  --project-root D:\path\to\project `
  --output D:\path\to\csdn-bundle

python prepare-csdn-draft/scripts/validate_csdn_bundle.py `
  --bundle D:\path\to\csdn-bundle
```

## 网页宣传视频

`build-web-promo-video` 将网页路径、公共 URL 或已有视频片段整理为可复现的完整视频包：

- Playwright 真实浏览器录制，并可为横版/竖版分别使用响应式视口；
- 可选文件配音或 Edge TTS、程序化 BGM、SRT 和按画幅生成的 ASS 字幕；
- H.264/AAC 的横竖版无字幕/字幕 MP4；
- 可编辑素材清单、联系表、FFprobe JSON/Markdown 质检报告。

该 Skill 需要 Node.js 20+、Playwright 浏览器，以及带 H.264/AAC 和 ASS 支持的 FFmpeg/
FFprobe。Edge TTS 仅在配置选择该提供方时需要 Python 依赖和网络。

```powershell
Set-Location build-web-promo-video/scripts
npm install
npx playwright install chromium

node build_promo_video.mjs `
  --config D:\path\to\video-project.json `
  --force
```

## 开发与验证

脚本只依赖 Python 标准库和系统 Git：

```powershell
python -m unittest discover -s tests -v
python C:\path\to\skill-creator\scripts\quick_validate.py github-safe-publish
python C:\path\to\skill-creator\scripts\quick_validate.py prepare-csdn-draft
python C:\path\to\skill-creator\scripts\quick_validate.py build-web-promo-video
```

## 适用边界

V1 针对“本地项目 → 用户已创建的 GitHub 仓库”。它不会创建 GitHub 仓库、Release、
Pages 或 CSDN 文章，也不代替平台级 Secret Scanning。非空远端默认阻断；只有远端分支
已经属于同一历史时，才允许通过显式参数执行普通 fast-forward 更新。

`prepare-csdn-draft` 只生成本地文章发布包，不访问 CSDN 账号、不控制浏览器、不保存网页
草稿，也不公开发布。图片排版与最终预览仍由作者本人确认。

`build-web-promo-video` 不登录或上传到视频平台，不自动取得第三方音乐、字体、商标、配音
或视频片段的使用权。FFprobe 参数通过后仍必须人工检查所有联系表和最终成片。

## License

[MIT](LICENSE)
