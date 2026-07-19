---
name: github-project-publisher
description: Publish a local Git project to an existing GitHub repository and optionally create a versioned GitHub Release with a source archive, release notes, explicit assets, SHA-256 checksums, and independent remote verification. Use when Codex needs an all-in-one, auditable workflow for committing, pushing, tagging, packaging, releasing, or verifying an open-source project on GitHub.
---

# GitHub Project Publisher

Publish one project through one user-facing Skill. Keep the implementation modular: inspect the
local project, check the target remote, prepare a versioned Release package, perform ordinary Git
operations, optionally call the authenticated GitHub CLI, and verify the remote result.

This Skill targets an already existing GitHub repository. It does not create repositories, change
organization settings, deploy Pages, or alter unrelated remotes.

## Workflow

### 1. Inspect the project

Confirm the exact Git root, current branch, `HEAD`, worktree status, remotes, candidate files,
`.gitignore`, README, LICENSE, likely credentials, and files over GitHub's 100 MiB limit. Read
[references/safety-policy.md](references/safety-policy.md) before any external write.

Stop on blockers. Findings contain path and rule only; never print matched secret values.

### 2. Inspect the target

Require the exact GitHub URL and a matching `--confirm-repository OWNER/REPOSITORY`. Inspect the
target branch with `git ls-remote`.

- Empty target: normal first publication path.
- Non-empty target: require `--allow-existing`, fetch it, and prove it is an ancestor of local
  `HEAD` before pushing.
- Existing local or remote tag: stop. Never replace tags or force-push.

### 3. Preview the complete operation

Run without `--execute` first:

```powershell
python <skill>\scripts\publish_project.py `
  --project D:\path\to\project `
  --remote https://github.com/OWNER/REPOSITORY `
  --confirm-repository OWNER/REPOSITORY `
  --branch main `
  --commit-message "feat: publish project" `
  --receipt D:\path\to\dry-run.json
```

Review the JSON receipt: audit findings, candidate count, target branch state, version source,
planned operations, Release assets, and artifact directory. Dry-run never stages or changes Git.

### 4. Publish the branch

With explicit authorization, add `--execute`. The Skill:

1. Adds the requested remote only when it does not exist; refuses to rewrite a different URL.
2. Fetches and checks fast-forward safety for an existing branch.
3. Stages the audited project boundary and runs `git diff --cached --check`.
4. Commits staged changes when present.
5. Pushes with ordinary `git push --set-upstream`, never a force option.

### 5. Create a versioned Release when requested

Add `--release` and `--version 1.2.3` (or provide a version in `package.json`, `pyproject.toml`, or
`Cargo.toml`). The Skill normalizes the tag to `v1.2.3`, derives notes from Git history, creates a
source archive from final `HEAD`, copies explicitly supplied assets, writes `SHA256SUMS.txt`, then
creates the Release through an authenticated `gh` CLI.

```powershell
python <skill>\scripts\publish_project.py `
  --project D:\path\to\project `
  --remote https://github.com/OWNER/REPOSITORY `
  --confirm-repository OWNER/REPOSITORY `
  --allow-existing `
  --version 1.2.3 `
  --release `
  --asset dist\project.zip `
  --execute `
  --receipt D:\path\to\publish-receipt.json
```

Read [references/github-cli.md](references/github-cli.md) before using `--release`. The GitHub
CLI is not needed for branch-only publication.

### 6. Verify independently

Run after publishing:

```powershell
python <skill>\scripts\verify_publish.py `
  --project D:\path\to\project `
  --remote https://github.com/OWNER/REPOSITORY `
  --branch main `
  --tag v1.2.3
```

Require local `HEAD` to match the remote branch and the requested tag to exist. Keep the receipt and
Release artifact directory as evidence.

## Modes

- **Branch-only**: audit, commit, push, and verify.
- **Release**: branch-only plus version detection, notes, source archive, explicit assets,
  checksums, tag, GitHub Release, and verification.
- **Local test**: use `--allow-local-remote` with a `file://` bare remote; this is for reproducible
  tests, not production publishing.

## Non-negotiable rules

- Never request or print tokens, passwords, private keys, cookies, or credential values.
- Never publish when the audit finds likely credentials or files over 100 MiB.
- Never rewrite an existing remote URL silently.
- Never push with `--force` or replace an existing tag.
- Never treat a GitHub CLI exit code as proof without checking the receipt and remote state.
- Do not create the GitHub repository, Releases, Pages, issues, or pull requests unless the user
  explicitly requests the corresponding operation.
- Write generated Release files outside the project by default.
- Do not claim a cross-platform build or test result that was not actually run.

## Resources

- `scripts/publisher_lib.py`: shared audit, Git, remote, archive, checksum, and verification logic.
- `scripts/publish_project.py`: dry-run and execute orchestrator.
- `scripts/verify_publish.py`: independent branch/tag verification.
- `references/safety-policy.md`: authorization and external-write rules.
- `references/release-schema.md`: receipt and artifact contract.
- `references/github-cli.md`: Release authentication requirements.
