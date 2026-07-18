# Publication safety policy

Read this file before any external write.

## Authorization

- Require an exact local project root and an exact GitHub repository URL.
- Treat an explicit instruction to upload, publish, push, or open-source the scoped project as
  authorization for ordinary commits and pushes to that target.
- Treat review, diagnosis, planning, or “is this possible?” as read-only.
- Keep repository creation, Releases, Pages, issues, pull requests, and account settings outside
  scope unless the user asks for them separately.

## Credentials

- Use an installed Git credential helper, SSH agent, or existing authenticated environment.
- Never ask for or echo a personal access token, password, private key, cookie, or credential file.
- Redact findings by category, path, and line number. Never copy the matched value into output.
- Block the publication when a likely credential is tracked or is a candidate for staging.
- Explain that removing a committed secret from the latest tree does not revoke it; advise rotation
  and history cleanup when exposure may have occurred.

## Local state

- Inspect the entire worktree, staged diff, unstaged diff, untracked files, remotes, and branch.
- Preserve unrelated user edits. Do not reset, clean, delete, or rewrite them.
- Do not assume ignored content is disposable.
- Do not rewrite an existing remote URL. Add the requested remote under an unused name only when
  that choice is explicit and useful.

## Remote state

- Prefer a user-created empty repository for first publication.
- Refuse to push over a non-empty repository by default.
- Permit `--allow-existing` only when the target branch is already part of the same local Git
  history and the update is fast-forward.
- If the remote contains unrelated commits, clone it separately or integrate histories through a
  user-approved workflow. Do not use force push, orphan replacement, or automatic unrelated-history
  merges.
- Match the URL's parsed `owner/repository` against a separately provided confirmation string.

## Commit and push

- Stage only the reviewed project boundary. Honor ignore rules and scanner blockers.
- Run `git diff --cached --check` before committing.
- Use a normal commit and normal push. Never pass any force option.
- Verify that local `HEAD` equals the SHA advertised by the target remote branch.
- If pushing fails after a local commit, report that the commit exists locally and do not claim the
  repository is published.
