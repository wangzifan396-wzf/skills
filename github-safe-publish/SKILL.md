---
name: github-safe-publish
description: Inspect a local project, decide what should and should not be uploaded, detect likely secrets and oversized files, check GitHub remote safety, prepare repository essentials, and publish with ordinary non-force Git operations only after explicit authorization. Use when a user asks Codex to upload, open-source, initialize, or update a local project in a GitHub repository and provides or requests help with a GitHub repository URL.
---

# GitHub Safe Publish

Turn a local project into a reviewed GitHub publication. Separate inspection from mutation, keep
claims traceable to the repository, and leave a machine-readable publication receipt.

## Workflow

### 1. Establish scope and authority

Identify the exact local project root and target GitHub repository. Treat a request such as
"publish/upload this project to this repository" as authorization to commit and push within that
scope. If the user only asks for a review, plan, or explanation, stop after inspection.

Read [references/safety-policy.md](references/safety-policy.md) before any command that can commit,
push, change a remote, or alter external state. Never request that a user paste a token into chat;
use the installed Git credential helper or an already authenticated environment.

### 2. Inspect without modifying the project

Run the scanner and place its outputs outside the project unless the user wants to keep them:

```text
python <skill>/scripts/inspect_project.py <project-root> \
  --json-out <audit.json> --report-out <audit.md>
```

Review all blocker and warning records. The JSON is the authoritative manifest; it lists every
candidate file, ignored path returned by Git, project entry points, repository readiness, byte
totals, and findings without printing secret values.

Inspect `git status --short --branch`, `git diff`, `git diff --cached`, existing remotes, and recent
commits yourself. Preserve unrelated user changes and never delete files merely because the
scanner recommends excluding them.

### 3. Prepare the publication boundary

Resolve every blocker before staging. Remove real credentials from project files and rotate any
credential that may already have been exposed. Do not simply add an already tracked secret to
`.gitignore`; remove it from the Git index or history as appropriate.

Preview conservative ignore additions:

```text
python <skill>/scripts/prepare_gitignore.py <project-root>
```

Use `--write` only when the proposed entries fit the project. Preserve existing rules and keep
examples such as `.env.example` publishable. Do not automatically exclude `dist`, `build`, images,
or generated documentation because those can be intentional release artifacts.

Read [references/readiness-checklist.md](references/readiness-checklist.md) when README, LICENSE,
entry points, run instructions, or test instructions are missing. Add only project-specific,
factually verified content, then rerun the scanner.

### 4. Inspect the target GitHub repository

Run:

```text
python <skill>/scripts/inspect_remote.py <github-url> --json-out <remote.json>
```

Confirm that the parsed `owner/repository` exactly matches the user's target. An empty remote is
the normal first-publication path. For a non-empty remote, stop unless it is an existing publication
of the same local history. Never replace unrelated remote content.

### 5. Generate and review a dry-run

Run the publisher without `--execute`:

```text
python <skill>/scripts/publish_project.py \
  --project <project-root> \
  --remote <github-url> \
  --confirm-repository <owner/repository> \
  --commit-message <message> \
  --receipt <receipt.json>
```

Review the planned remote, branch, candidate count, repository status, and exact Git operations.
Show the user material blockers or scope surprises. A dry-run never initializes Git, stages,
commits, adds a remote, or pushes.

### 6. Publish only with explicit authorization

If the request already explicitly authorizes upload/publish, execute the reviewed command with
`--execute`. Otherwise ask for authorization first. The script requires the repository slug to be
retyped through `--confirm-repository`; this guards against pushing to a similarly named URL.

For an established publication, add `--allow-existing` only after confirming that the target
branch belongs to the same history. This flag still permits only a normal fast-forward push. Never
use `--force`, `--force-with-lease`, history rewriting, or destructive resets as part of this skill.

### 7. Verify and report

The publisher compares local `HEAD` with the target branch after pushing. Independently rerun:

```text
python <skill>/scripts/verify_publish.py \
  --project <project-root> --remote <github-url> --branch <branch>
```

Report the public repository URL, branch, commit SHA, whether a new commit was created, the remote
verification result, and any files intentionally left untracked. Do not claim success from a zero
exit code alone when the remote SHA was not observed.

## Non-negotiable gates

- Block likely secrets, private keys, credential files, and files over GitHub's 100 MiB limit.
- Never display matched credential values in logs, reports, or chat.
- Respect existing `.gitignore`; inspect tracked files even when a new ignore rule would match them.
- Never overwrite an existing remote URL silently.
- Never publish to a parsed slug different from `--confirm-repository`.
- Never invent test results, project features, license terms, or release claims.
- Never create a repository, GitHub Release, Pages deployment, issue, or message unless separately
  requested.
- Treat generated audit files as local evidence by default, not automatic project content.

## Supported cases

Support ordinary source repositories, static sites, single-file web projects, Node frontends,
Python projects, and repositories containing binary assets. For Git LFS, submodules, monorepo
subdirectory publication, protected branches, organization SSO, or unrelated non-empty remotes,
inspect and explain the required workflow instead of forcing the V1 publisher through it.

## Resources

- `scripts/inspect_project.py`: create the upload/exclusion manifest and readiness audit.
- `scripts/prepare_gitignore.py`: preview or append conservative ignore entries.
- `scripts/inspect_remote.py`: parse a GitHub URL and inspect remote refs without mutation.
- `scripts/publish_project.py`: dry-run by default; safely commit and push when explicitly executed.
- `scripts/verify_publish.py`: compare local and remote commit state after publication.
- `references/safety-policy.md`: required authorization and remote-history rules.
- `references/readiness-checklist.md`: project-specific README, license, and run/test checks.
- `references/troubleshooting.md`: read only when authentication, remote, branch, or size checks fail.
