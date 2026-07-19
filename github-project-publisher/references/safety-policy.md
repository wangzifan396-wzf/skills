# Safety policy

## Scope

This Skill publishes to an already existing GitHub repository supplied by the user. It does not
create repositories, alter organization settings, create Pages sites, or modify unrelated remotes.

## Default behavior

- Run without `--execute` first. Dry-run does not stage, commit, push, tag, or create a Release.
- Require `--confirm-repository OWNER/REPOSITORY` to match the parsed GitHub URL exactly.
- Refuse a non-empty remote unless `--allow-existing` is present and the remote branch is an
  ancestor of local `HEAD`.
- Refuse existing local or remote tags. Never replace a tag or use force push.
- Stage only the requested project boundary and respect `.gitignore`.
- Stop on likely credentials, private keys, and files over 100 MiB.

## Credentials

Use the installed Git credential helper, SSH agent, or authenticated GitHub CLI. Never request a
token, password, private key, browser cookie, or credential file in chat. Do not echo secret values
in receipts or reports.

## Release assets

Release archives and checksums are written outside the project by default. Explicit asset paths may
be supplied, but each file is checked for existence and GitHub's 100 MiB limit. The generated source
archive comes from the committed `HEAD`, so execute the commit before packaging the final Release.

## Verification

After a push, compare local `HEAD` with the target remote branch. When a tag is requested, require
the remote tag to exist. When a GitHub Release is requested, verify it with `gh release view` or the
GitHub CLI result and keep the receipt.
