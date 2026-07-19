# CSDN visual standard

Use this standard when the article has any cover or body visual.

## Cover

- Prefer 1920×1080 or another 16:9 image at least 1200 pixels wide.
- Communicate one topic at thumbnail size; avoid full paragraphs and tiny code.
- Use a short title, one supporting phrase, and at most a few verified metrics.
- Set the cover through CSDN's cover control. Do not repeat it in the first paragraph unless the
  image also carries information needed by the article.

## Body images

- Prefer 1600×900 for diagrams and data cards when 16:9 suits the content.
- Use real screenshots for runtime appearance and generated diagrams for relationships or exact
  mappings.
- Give each image a stable ASCII filename and a unique number.
- Place the Markdown image exactly where the reader needs it, followed by a concise caption.
- Ensure labels remain readable when the image is displayed around 800 CSS pixels wide.

## Evidence integrity

- Keep chart numbers in a structured JSON or other source file when practical.
- Do not turn configuration targets into measured results.
- Do not use an invented UI screenshot as proof of a real product state.
- Identify illustrative diagrams as diagrams; do not style them as telemetry screenshots.
- Preserve meaningful caveats in the caption or nearby text.

## Visual QA

Inspect every final file, not only the generator output log. Check:

- clipped or overlapping text;
- missing glyphs and mojibake;
- low-contrast labels;
- inconsistent numbers between article, data and image;
- stretched screenshots;
- incorrect image ordering;
- accidental secrets or personal information;
- blank placeholders presented as finished visuals.

The validator checks common dimensions and file presence. It cannot judge composition, factual
meaning, or whether a screenshot shows the intended application state.
