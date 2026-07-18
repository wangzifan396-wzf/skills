# Troubleshooting

Read only the relevant section when a publication step fails.

## Authentication failed

- Run a read-only `git ls-remote` first.
- Confirm that the GitHub repository exists and that the current account can write to it.
- Use Git Credential Manager, `gh auth login` when GitHub CLI is available, or an SSH agent.
- Never paste a token into the remote URL or chat. Reject URLs containing embedded credentials.

## Remote is non-empty

- Inspect its branches and default branch.
- Fetch the target branch and determine whether it is an ancestor of local `HEAD`.
- Use `--allow-existing` only for the same history and a fast-forward update.
- For a GitHub-created README/license commit or unrelated history, stop and choose an explicit
  integration workflow. Never solve it with force push.

## Existing remote points elsewhere

- Preserve the remote.
- Confirm whether the user wants a new remote name or selected the wrong project.
- Do not silently run `git remote set-url`.

## File is too large

- Files above 100 MiB cannot be pushed through normal GitHub Git storage.
- Decide whether the file is generated and should be ignored, belongs in a release artifact, or
  requires Git LFS.
- Removing it from the current directory is insufficient if it already exists in commit history.

## Push rejected

- Keep the local commit intact.
- Fetch and inspect the remote change.
- Report whether the failure is authentication, branch protection, non-fast-forward history, or
  a server-side hook.
- Do not retry with a force option.

## Remote SHA does not match

- Query the exact `refs/heads/<branch>` ref.
- Compare it with `git rev-parse HEAD`.
- Do not report success until both values match or the user explicitly accepts a different release
  mechanism such as a pull request.
