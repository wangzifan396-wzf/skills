# Draft bundle schema

Use this reference when filling metadata or consuming package outputs.

## Metadata input

Start from `assets/metadata-template.json`.

Required fields:

- `articleType`: normally `原创`, unless the author intentionally selects another type.
- `category`: recommended CSDN category text.
- `summary`: reader-facing abstract.
- `tags`: array of 3-5 specific tags.
- `cover`: local cover path, relative to `--project-root` when provided.

Optional fields:

- `backupCategories`: alternative category strings.
- `alternativeTitles`: up to three alternatives.
- `repositoryUrl`: public project URL.
- `sourceCommit`: exact public commit when the article is tied to a revision.
- `notes`: human-only publication reminders.

The authoring Markdown H1 is the recommended title. If `title` is present in metadata, it must match
the H1 exactly.

## Image resolution

- Resolve Markdown body images relative to the authoring Markdown file.
- Resolve metadata `cover` relative to `--project-root`; without that option, resolve it relative to
  the metadata file.
- Preserve remote HTTP(S) images in the text and report them as warnings because availability and
  hotlink policy are outside the bundle.
- Reject missing local images.

## Generated output

```text
bundle/
├── article-source.md
├── article-csdn.md
├── publish-metadata.json
├── image-map.json
├── human-upload-checklist.md
├── validation-report.json
├── validation-report.md
└── images/
    ├── cover.jpg
    ├── 01-first-body-image.jpg
    └── 02-second-body-image.png
```

`article-source.md` preserves the original authoring file. `article-csdn.md` removes recognized
internal publishing notes and replaces local image Markdown with visible markers:

```text
> 【配图 01：请上传 images/01-first-body-image.jpg 后删除本行】
```

`image-map.json` maps each marker to the original source reference, copied file, alt text, caption, byte size,
dimensions and insertion order. `human-upload-checklist.md` repeats the exact publishing sequence.

## Overwrite behavior

The packager refuses to overwrite generated files by default. `--force` replaces only the known
generated files and numbered images in the selected bundle. It never recursively deletes the output
directory or unrelated files.
