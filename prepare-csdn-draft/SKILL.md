---
name: prepare-csdn-draft
description: Create evidence-backed Chinese CSDN technical article drafts and package them for fast human publishing, including a polished Markdown source, clean paste-ready copy, cover and body-image inventory, exact image placement markers, publication metadata, upload checklist, and validation report. Use when a user asks Codex to write, improve, package, or prepare a CSDN blog post, project launch article, technical tutorial, open-source announcement, or publishable draft without operating the CSDN website or account.
---

# Prepare CSDN Draft

Produce a complete local article bundle that a human can publish quickly. Keep writing judgment in
the agent, make packaging and validation deterministic, and never operate the CSDN website.

## Workflow

### 1. Establish the article scope

Identify the intended reader, article type, primary takeaway, source project, public links, and
available evidence. Inspect the relevant code, documentation, test output, screenshots, data, and
existing articles before choosing an angle. Avoid repeating an existing article unless the user
explicitly wants a revision or follow-up.

Read [references/article-standard.md](references/article-standard.md) before drafting. Build a small
fact table for every version, count, benchmark, commit, feature, limitation, and repository claim.
Remove claims that cannot be traced to code, a command result, a public URL, or user-provided facts.

### 2. Plan the story and visuals

Choose one primary argument. Prefer a real problem, design decision, workflow, experiment, or
reusable method over a feature inventory. Plan the title, abstract, section outline, evidence,
examples, limitations, and call to action together.

Read [references/visual-standard.md](references/visual-standard.md) when the article needs a cover,
screenshots, diagrams, or charts. Reuse real project visuals where useful. Generate diagrams from
structured data when exact labels or repeated numbers matter. Never use a blank placeholder or an
invented dashboard as evidence.

### 3. Write the authoring Markdown

Create one UTF-8 Markdown source with:

1. A single H1 title.
2. An optional top blockquote beginning with `发布说明（发布时可删除）`.
3. A concise opening that states the problem and article payoff.
4. Evidence-backed sections with copyable code or commands where useful.
5. Local body-image Markdown at the exact intended insertion positions.
6. A caption immediately after each body image.
7. Honest limitations and a restrained project link or call to action.
8. An optional final `## 发布信息（发布时可删除）` section containing title alternatives, tags,
   category, cover path, and publication reminders.

Do not repeat the cover as the first body image unless it contains information needed by the
article. Keep internal publishing notes outside the reader-facing body.

### 4. Prepare publication metadata

Copy `assets/metadata-template.json` beside the authoring source and fill every required field.
Keep paths relative to the project root when possible. Follow
[references/bundle-schema.md](references/bundle-schema.md) for exact fields and output semantics.

Use 3-5 specific tags. Provide one recommended title and up to three meaningful alternatives. Write
an abstract that states the concrete problem, method, evidence, and result rather than repeating the
title.

### 5. Package the draft

Run:

```text
python <skill>/scripts/package_csdn_draft.py \
  --article <authoring.md> \
  --metadata <metadata.json> \
  --project-root <project-root> \
  --output <bundle-directory>
```

The packager must copy and number local images, remove the top release-note block and final publish
information section from the paste-ready body, replace each local image with a searchable human
upload marker, and create the metadata, image map, checklist, and validation report. It must not
modify the authoring source.

Use `--force` only to overwrite files previously generated in the same bundle directory. Never
delete unrelated files from an output directory.

### 6. Validate and inspect

Run the standalone validator after every material edit:

```text
python <skill>/scripts/validate_csdn_bundle.py \
  --bundle <bundle-directory> \
  --json-out <validation.json> \
  --report-out <validation.md>
```

Resolve every blocker. Review warnings rather than mechanically suppressing them. Visually inspect
the cover and every body image; dimension checks do not detect clipped text, bad hierarchy,
misleading charts, or unreadable mobile details.

### 7. Hand off for human publishing

Deliver these files together:

- `article-source.md`: evidence-preserving authoring copy.
- `article-csdn.md`: clean copy with numbered `【配图】` markers.
- `publish-metadata.json`: title, abstract, category, tags, links, and cover.
- `image-map.json`: source, packaged filename, marker, caption, size, and dimensions.
- `human-upload-checklist.md`: exact CSDN paste/upload sequence.
- `validation-report.json` and `validation-report.md`.
- `images/`: numbered cover and body images.

Tell the user to paste `article-csdn.md`, search each `【配图 NN】` marker, upload the corresponding
file, remove the marker, set the cover and metadata, preview, and save or publish manually.

## Non-negotiable rules

- Do not log in to CSDN, control a browser, read cookies, save a web draft, or publish an article.
- Do not invent project metrics, benchmark results, users, stars, dates, commits, or test outcomes.
- Do not leave TODO, TBD, broken image paths, unmatched fences, or local absolute paths in the
  paste-ready article.
- Do not treat generated artwork as runtime evidence.
- Do not include secrets, private repository URLs, session data, or private user information.
- Do not copy third-party articles or visuals without permission and attribution.
- Do not claim a legal, security, performance, or compatibility guarantee beyond the evidence.
- Keep publication notes and human instructions out of the reader-facing paste-ready body.

## Resources

- `scripts/package_csdn_draft.py`: build the self-contained human-publishable bundle.
- `scripts/validate_csdn_bundle.py`: validate Markdown, metadata, markers, paths, and image dimensions.
- `references/article-standard.md`: use before planning and drafting.
- `references/visual-standard.md`: use when selecting or generating any article visual.
- `references/bundle-schema.md`: use before filling metadata or interpreting bundle outputs.
- `assets/metadata-template.json`: copy and customize for each article.
