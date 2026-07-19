# GitHub CLI requirements

Repository push uses ordinary Git and the user's configured credential helper or SSH agent.

Creating a GitHub Release requires the GitHub CLI (`gh`) to be installed and authenticated. The
publisher looks for `gh` on `PATH`; set `GH_BIN` when it lives elsewhere. The Skill does not read or
print the authentication token.

Typical checks before a real Release:

```powershell
gh auth status
gh repo view OWNER/REPOSITORY
```

The user must still explicitly pass `--release --execute`. Without `--release`, the Skill only
publishes the branch and never creates a GitHub Release.
