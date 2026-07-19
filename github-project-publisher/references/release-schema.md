# Release output schema

The publisher writes a JSON receipt with:

- `status`: `planned`, `published`, or `blocked`;
- `project`, `remote`, `repository`, `branch`, and `remoteName`;
- `audit`: candidate files, byte totals, readiness, and redacted findings;
- `remoteAudit`: target branch state before mutation;
- `version` and `releasePlan` when a Release is requested;
- `operations`: the exact planned or executed Git operations;
- `release.artifacts`: artifact paths, byte sizes, and SHA-256 values;
- `verification`: local/remote branch and tag comparison.

Generated Release directories contain:

```text
RELEASE_NOTES.md
<project>-v1.2.3.zip
<explicit-asset-files>
SHA256SUMS.txt
```

The source archive is created with `git archive` from the final committed `HEAD`. It is therefore
reproducible from the repository commit and does not include ignored build caches or credentials.
