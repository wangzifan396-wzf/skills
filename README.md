# Codex Skills

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)

这里收录可安装、可审计、带确定性脚本的 Codex Skills。首个 Skill 是
`github-safe-publish`：把本地项目发布到用户已创建的 GitHub 仓库，同时在提交前检查
密钥、缓存、日志、大文件、开源文档和远端状态。

## Skills

| Skill | 用途 | 状态 |
| --- | --- | --- |
| [`github-safe-publish`](github-safe-publish/) | 审计本地项目，生成上传/排除清单，并在明确授权后安全提交、推送和校验 GitHub 仓库 | V1 |

## 安装

只安装当前 Skill：

```powershell
git clone https://github.com/wangzifan396-wzf/skills.git
Copy-Item -Recurse .\skills\github-safe-publish "$HOME\.codex\skills\github-safe-publish"
```

macOS / Linux：

```bash
git clone https://github.com/wangzifan396-wzf/skills.git
cp -R skills/github-safe-publish ~/.codex/skills/github-safe-publish
```

重启 Codex 后，可以这样调用：

```text
使用 $github-safe-publish，检查当前项目，并发布到
https://github.com/OWNER/REPOSITORY 。
```

用户必须明确给出目标仓库并授权推送。Skill 不会索要聊天中的 Token，不会强制推送，
也不会静默覆盖非空远端。

## 它会检查什么

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

## 开发与验证

脚本只依赖 Python 标准库和系统 Git：

```powershell
python -m unittest discover -s tests -v
python C:\path\to\skill-creator\scripts\quick_validate.py github-safe-publish
```

## 适用边界

V1 针对“本地项目 → 用户已创建的 GitHub 仓库”。它不会创建 GitHub 仓库、Release、
Pages 或 CSDN 文章，也不代替平台级 Secret Scanning。非空远端默认阻断；只有远端分支
已经属于同一历史时，才允许通过显式参数执行普通 fast-forward 更新。

## License

[MIT](LICENSE)
